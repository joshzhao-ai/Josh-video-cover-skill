#!/usr/bin/env python3
"""Execute Dreamina requests from a v2 cover manifest without recropping."""

import argparse
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

from PIL import Image


TRANSIENT_ERRORS = (
    "deadline exceeded",
    "context cancellation",
    "connection reset by peer",
    "read tcp",
    "timeout",
)


def read_json(path):
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def run(command):
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = completed.stdout or ""
    if completed.returncode:
        raise RuntimeError(output.strip() or f"Command failed: {' '.join(command)}")
    return output


def extract_submit_id(output):
    for pattern in (
        r'"submit_id"\s*:\s*"([^"]+)"',
        r"submit_id\s*[:=]\s*([A-Za-z0-9_.:-]+)",
    ):
        match = re.search(pattern, output)
        if match:
            return match.group(1)
    return ""


def extract_status(output):
    match = re.search(r'"gen_status"\s*:\s*"([^"]+)"', output)
    if match:
        return match.group(1).lower()
    lower = output.lower()
    for status in ("success", "querying", "fail"):
        if status in lower:
            return status
    return ""


def media_files(path):
    extensions = {".jpg", ".jpeg", ".png", ".webp"}
    return sorted(
        (item for item in Path(path).rglob("*") if item.is_file() and item.suffix.lower() in extensions),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )


def validate_ratio(path, ratio):
    expected = 3 / 4 if ratio == "3:4" else 4 / 3
    with Image.open(path) as image:
        actual = image.width / image.height
        if abs(actual - expected) > 0.05:
            raise RuntimeError(
                f"Dreamina returned {image.width}x{image.height} for requested {ratio}; refusing to crop it silently."
            )


def save_native(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image.load()
        if target.suffix.lower() in {".jpg", ".jpeg"}:
            image.convert("RGB").save(target, quality=95, subsampling=0)
        else:
            image.save(target)


def submit_and_download(command, download_dir, timeout, interval):
    submit_output = run(command)
    submit_id = extract_submit_id(submit_output)
    if not submit_id:
        raise RuntimeError("Dreamina submit did not return submit_id.\n" + submit_output.strip())
    # Retries must never consume a file left by a previous submission.
    Path(download_dir).mkdir(parents=True, exist_ok=True)
    attempt_dir = Path(tempfile.mkdtemp(prefix="attempt-", dir=download_dir))
    started = time.time()
    last_output = submit_output
    while time.time() - started <= timeout:
        try:
            last_output = run([
                command[0],
                "query_result",
                "--submit_id",
                submit_id,
                "--download_dir",
                str(attempt_dir),
            ])
        except RuntimeError as exc:
            last_output = str(exc)
            if not any(token in last_output.lower() for token in TRANSIENT_ERRORS):
                raise
            time.sleep(interval)
            continue
        status = extract_status(last_output)
        if status == "fail":
            raise RuntimeError("Dreamina generation failed.\n" + last_output.strip())
        files = media_files(attempt_dir)
        if files:
            return files[0]
        time.sleep(interval)
    raise RuntimeError(f"Dreamina generation timed out for submit_id={submit_id}.\n{last_output.strip()}")


def main():
    parser = argparse.ArgumentParser(description="Execute native-ratio Dreamina requests from cover_requests.json.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--route", action="append", default=[])
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).expanduser().resolve()
    manifest = read_json(manifest_path)
    wanted = set(args.route)
    routes = [item for item in manifest.get("routes", []) if not wanted or item.get("name") in wanted]
    if wanted - {item.get("name") for item in routes}:
        raise SystemExit("Unknown routes: " + ", ".join(sorted(wanted - {item.get("name") for item in routes})))
    if not routes:
        raise SystemExit("No Dreamina routes found in manifest.")

    for item in routes:
        if item.get("engine") != "dreamina" or not item.get("dreamina_command"):
            raise SystemExit(f"Route {item.get('name')} is not an executable Dreamina request.")
        target = Path(item["expected_output"]).expanduser().resolve()
        if target.exists() and not args.force:
            validate_ratio(target, item["ratio"])
            print(target)
            continue
        download_dir = manifest_path.parent / ".dreamina-downloads" / item["name"]
        download_dir.mkdir(parents=True, exist_ok=True)
        source = submit_and_download(item["dreamina_command"], download_dir, args.timeout, args.interval)
        validate_ratio(source, item["ratio"])
        save_native(source, target)
        validate_ratio(target, item["ratio"])
        print(target)


if __name__ == "__main__":
    main()
