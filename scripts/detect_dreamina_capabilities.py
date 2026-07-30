#!/usr/bin/env python3
"""Discover the locally installed Dreamina image-model surface without guessing."""

import argparse
import json
import re
import subprocess
from pathlib import Path


def run(cli, *args):
    completed = subprocess.run([cli, *args], text=True, capture_output=True)
    return (completed.stdout or "") + (completed.stderr or "")


def parse_models(help_text):
    match = re.search(r"model_version:\s*([^\n]+)", help_text, re.IGNORECASE)
    if not match:
        return []
    return re.findall(r"\d+(?:\.\d+)+(?:[-_ ]?(?:pro|lite))?", match.group(1), re.IGNORECASE)


def rank(model):
    numbers = tuple(int(item) for item in re.findall(r"\d+", model))
    flavor = 2 if re.search(r"pro", model, re.IGNORECASE) else 1 if re.search(r"lite", model, re.IGNORECASE) else 0
    return numbers, flavor


def resolve(models, requested):
    if requested != "auto":
        if requested not in models:
            raise SystemExit(f"Requested Dreamina model {requested!r} is not supported by this installed CLI: {', '.join(models) or 'none detected'}")
        return requested
    if not models:
        raise SystemExit("Could not detect supported Dreamina image models from the installed CLI.")
    return max(models, key=rank)


def main():
    parser = argparse.ArgumentParser(description="Inspect local Dreamina model support.")
    parser.add_argument("--cli", default=str(Path.home() / ".local/bin/dreamina"))
    parser.add_argument("--requested", default="auto")
    args = parser.parse_args()
    cli = str(Path(args.cli).expanduser())
    t2i = run(cli, "text2image", "-h")
    i2i = run(cli, "image2image", "-h")
    text_models = parse_models(t2i)
    image_models = parse_models(i2i)
    shared = sorted(set(text_models).intersection(image_models), key=rank)
    chosen = resolve(shared or text_models, args.requested)
    payload = {
        "cli": cli,
        "text2image_models": text_models,
        "image2image_models": image_models,
        "shared_image_models": shared,
        "requested_model": args.requested,
        "resolved_model": chosen,
        "pro_available": bool(re.search(r"pro", chosen, re.IGNORECASE)),
        "note": "Use the resolved model only. Do not label a generic 5.0 build as Pro unless the CLI reports a Pro model string.",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
