#!/usr/bin/env python3
import argparse
import base64
import json
import os
import time
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image


CANVAS = (1080, 1440)


def cover_crop(image):
    image = image.convert("RGB")
    src_ratio = image.width / image.height
    dst_ratio = CANVAS[0] / CANVAS[1]
    if src_ratio > dst_ratio:
        new_width = int(image.height * dst_ratio)
        left = (image.width - new_width) // 2
        image = image.crop((left, 0, left + new_width, image.height))
    else:
        new_height = int(image.width / dst_ratio)
        top = (image.height - new_height) // 2
        image = image.crop((0, top, image.width, top + new_height))
    return image.resize(CANVAS, Image.Resampling.LANCZOS)


def value_at_path(payload, path):
    current = payload
    for part in path.split("."):
        if isinstance(current, list):
            current = current[int(part)]
        else:
            current = current[part]
    return current


def first_available(payload):
    paths = [
        "data.0.b64_json",
        "data.0.url",
        "b64_json",
        "base64",
        "image",
        "url",
        "image_url",
        "images.0.b64_json",
        "images.0.base64",
        "images.0.url",
    ]
    custom = os.getenv("VCG_IMAGE_RESPONSE_PATH")
    if custom:
        paths.insert(0, custom)
    for path in paths:
        try:
            value = value_at_path(payload, path)
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        if value:
            return value
    raise ValueError("Could not find an image URL or base64 field in the API response.")


def image_from_value(value):
    if isinstance(value, dict):
        value = value.get("url") or value.get("b64_json") or value.get("base64") or value.get("image")
    if not isinstance(value, str):
        raise ValueError("Image response value is not a string.")
    if value.startswith("http://") or value.startswith("https://"):
        response = requests.get(value, timeout=120)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    if value.startswith("data:image"):
        value = value.split(",", 1)[1]
    return Image.open(BytesIO(base64.b64decode(value)))


def reference_data_url(path):
    if not path:
        return None
    path = Path(path).expanduser()
    if not path.exists():
        return None
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def call_image_api(prompt, reference_image):
    api_url = os.getenv("VCG_IMAGE_API_URL", "https://ark.cn-beijing.volces.com/api/v3/images/generations")
    api_key = os.getenv("VCG_IMAGE_API_KEY")
    model = os.getenv("VCG_IMAGE_MODEL", "doubao-seedream-5-0-260128")
    size = os.getenv("VCG_IMAGE_SIZE", "2K")
    if not api_url or not api_key:
        raise SystemExit("Set VCG_IMAGE_API_KEY. Optionally set VCG_IMAGE_API_URL and VCG_IMAGE_MODEL.")

    body = {
        "model": model,
        "prompt": prompt,
        "sequential_image_generation": "disabled",
        "response_format": "url",
        "size": size,
        "stream": False,
        "watermark": False,
        "n": 1,
    }
    if reference_image and os.getenv("VCG_IMAGE_INCLUDE_REFERENCE", "").lower() in {"1", "true", "yes"}:
        body["reference_image"] = reference_image

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    retries = int(os.getenv("VCG_IMAGE_API_RETRIES", "3"))
    last_error = None
    for attempt in range(retries + 1):
        response = requests.post(api_url, headers=headers, json=body, timeout=240)
        if response.status_code not in {429, 500, 502, 503, 504}:
            response.raise_for_status()
            return image_from_value(first_available(response.json()))
        last_error = requests.HTTPError(f"{response.status_code} retryable image API error", response=response)
        if attempt < retries:
            time.sleep(min(45, 8 * (attempt + 1)))
    raise last_error


def main():
    parser = argparse.ArgumentParser(description="Generate AI cover images from prompts using a configurable image API.")
    parser.add_argument("--prompts", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--reference-frame")
    args = parser.parse_args()

    prompts = json.loads(Path(args.prompts).expanduser().read_text(encoding="utf-8"))
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    reference_frame = args.reference_frame or prompts.get("person_reference")
    reference_image = reference_data_url(reference_frame)

    for variant in prompts["variants"]:
        name = variant["name"]
        image = call_image_api(variant["prompt"], reference_image)
        image = cover_crop(image)
        image.save(output_dir / f"{name}.jpg", quality=94, subsampling=0)


if __name__ == "__main__":
    main()
