#!/usr/bin/env python3
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


def detect_face_cv2(image_path):
    try:
        import cv2
    except Exception:
        return None

    image = cv2.imread(str(image_path))
    if image is None:
        return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(str(cascade_path))
    faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    if len(faces) == 0:
        return None
    h, w = gray.shape[:2]
    cx, cy = w / 2, h / 2
    faces = sorted(faces, key=lambda box: abs((box[0] + box[2] / 2) - cx) + abs((box[1] + box[3] / 2) - cy))
    x, y, fw, fh = faces[0]
    return x, y, fw, fh, w, h


def crop_from_face(image, face):
    x, y, fw, fh, w, h = face
    cx = x + fw / 2
    top = max(0, y - fh * 1.3)
    bottom = min(h, y + fh * 5.2)
    crop_h = bottom - top
    crop_w = min(w, crop_h * 0.82)
    left = max(0, min(w - crop_w, cx - crop_w / 2))
    return image.crop((int(left), int(top), int(left + crop_w), int(bottom)))


def central_portrait_crop(image):
    w, h = image.size
    crop_w = int(w * 0.46)
    crop_h = int(h * 0.9)
    left = (w - crop_w) // 2
    top = int(h * 0.04)
    return image.crop((left, top, left + crop_w, min(h, top + crop_h)))


def feather_alpha(image):
    image = image.convert("RGBA")
    w, h = image.size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((4, 4, w - 4, h - 4), radius=max(24, w // 16), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(max(3, w // 80)))
    image.putalpha(mask)
    return image


def main():
    parser = argparse.ArgumentParser(description="Create a real-person reference crop from a video frame.")
    parser.add_argument("--frame", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--transparent", action="store_true", help="Write a feathered transparent PNG.")
    args = parser.parse_args()

    frame = Path(args.frame).expanduser().resolve()
    if not frame.exists():
        raise SystemExit(f"Frame not found: {frame}")
    image = Image.open(frame).convert("RGB")
    face = detect_face_cv2(frame)
    crop = crop_from_face(image, face) if face else central_portrait_crop(image)
    if args.transparent:
        crop = feather_alpha(crop)
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    crop.save(output)


if __name__ == "__main__":
    main()
