#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from PIL import Image


TOLERANCE = 0.05


def check_image(path, expected_ratio, ratio_label):
    item = {
        "file": str(path),
        "exists": path.exists(),
        "openable": False,
        "width": None,
        "height": None,
        "aspect_ratio": None,
        "passed": False,
        "errors": [],
    }
    if not path.exists():
        item["errors"].append("missing")
        return item
    try:
        with Image.open(path) as image:
            item["openable"] = True
            item["width"], item["height"] = image.size
            item["aspect_ratio"] = round(item["width"] / item["height"], 4)
    except Exception as exc:
        item["errors"].append(f"unopenable: {exc}")
        return item

    if abs(item["aspect_ratio"] - expected_ratio) > TOLERANCE:
        item["errors"].append(f"aspect_ratio_not_{ratio_label.replace(':', '_')}")
    if item["width"] < 600 or item["height"] < 800:
        item["errors"].append("resolution_too_small")
    item["passed"] = not item["errors"]
    return item


def main():
    parser = argparse.ArgumentParser(description="Check generated cover files.")
    parser.add_argument("--covers-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--ratio", default="3:4", choices=["3:4", "4:3"])
    parser.add_argument("--expected-count", type=int, default=0)
    args = parser.parse_args()

    covers_dir = Path(args.covers_dir).expanduser().resolve()
    legacy_paths = [covers_dir / name for name in ["info-heavy.jpg", "visual-heavy.jpg", "balanced.jpg"]]
    if covers_dir.exists() and all(path.exists() for path in legacy_paths):
        images = legacy_paths
    elif covers_dir.exists():
        extensions = {".jpg", ".jpeg", ".png", ".webp"}
        images = sorted(
            path for path in covers_dir.iterdir()
            if path.is_file() and path.suffix.lower() in extensions and "contact" not in path.stem.lower()
        )
    else:
        images = []
    expected_count = args.expected_count or (3 if args.ratio == "3:4" else 2)
    expected_ratio = 3 / 4 if args.ratio == "3:4" else 4 / 3
    results = [check_image(path, expected_ratio, args.ratio) for path in images]
    count_ok = len(results) == expected_count
    report = {
        "passed": count_ok and all(item["passed"] for item in results),
        "ratio": args.ratio,
        "expected_count": expected_count,
        "actual_count": len(results),
        "count_ok": count_ok,
        "results": results,
    }
    Path(args.output).expanduser().write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
