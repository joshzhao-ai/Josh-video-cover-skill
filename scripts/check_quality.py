#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from PIL import Image


EXPECTED = 3 / 4
TOLERANCE = 0.05


def check_image(path):
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

    if abs(item["aspect_ratio"] - EXPECTED) > TOLERANCE:
        item["errors"].append("aspect_ratio_not_3_4")
    if item["width"] < 600 or item["height"] < 800:
        item["errors"].append("resolution_too_small")
    item["passed"] = not item["errors"]
    return item


def main():
    parser = argparse.ArgumentParser(description="Check generated cover files.")
    parser.add_argument("--covers-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    covers_dir = Path(args.covers_dir).expanduser().resolve()
    expected = ["info-heavy.jpg", "visual-heavy.jpg", "balanced.jpg"]
    results = [check_image(covers_dir / name) for name in expected]
    report = {
        "passed": all(item["passed"] for item in results),
        "results": results,
    }
    Path(args.output).expanduser().write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
