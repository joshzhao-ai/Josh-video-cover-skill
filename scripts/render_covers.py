#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


CANVAS = (1080, 1440)
SAFE = 72


FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


PALETTES = {
    "info-heavy": {
        "accent": (255, 214, 64),
        "accent2": (38, 198, 218),
        "text": (255, 255, 255),
        "shadow": (0, 0, 0),
        "overlay": (0, 0, 0, 128),
    },
    "visual-heavy": {
        "accent": (255, 92, 92),
        "accent2": (86, 214, 153),
        "text": (255, 255, 255),
        "shadow": (0, 0, 0),
        "overlay": (0, 0, 0, 78),
    },
    "balanced": {
        "accent": (86, 214, 153),
        "accent2": (255, 214, 64),
        "text": (255, 255, 255),
        "shadow": (0, 0, 0),
        "overlay": (0, 0, 0, 104),
    },
}


def load_font(size):
    for candidate in FONT_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size, index=0)
            except OSError:
                continue
    return ImageFont.load_default()


def cover_crop(image, size=CANVAS):
    image = image.convert("RGB")
    src_ratio = image.width / image.height
    dst_ratio = size[0] / size[1]
    if src_ratio > dst_ratio:
        new_width = int(image.height * dst_ratio)
        left = (image.width - new_width) // 2
        image = image.crop((left, 0, left + new_width, image.height))
    else:
        new_height = int(image.width / dst_ratio)
        top = (image.height - new_height) // 2
        image = image.crop((0, top, image.width, top + new_height))
    return image.resize(size, Image.Resampling.LANCZOS)


def text_width(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font, stroke_width=0)
    return box[2] - box[0]


def wrap_title(draw, title, font, max_width):
    if " " in title.strip():
        words = title.split()
        lines = []
        current = ""
        for word in words:
            trial = f"{current} {word}".strip()
            if text_width(draw, trial, font) <= max_width or not current:
                current = trial
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    lines = []
    current = ""
    for char in title:
        trial = current + char
        if text_width(draw, trial, font) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


def fit_title(draw, title, max_width, max_lines, start_size):
    size = start_size
    while size >= 48:
        font = load_font(size)
        lines = wrap_title(draw, title, font, max_width)
        if len(lines) <= max_lines:
            return font, lines
        size -= 6
    font = load_font(48)
    return font, wrap_title(draw, title, font, max_width)[:max_lines]


def draw_text_block(draw, title, xy, width, font_size, max_lines, palette, align="left"):
    font, lines = fit_title(draw, title, width, max_lines, font_size)
    line_gap = max(10, font.size // 10)
    line_height = font.size + line_gap
    x, y = xy
    for line in lines:
        line_width = text_width(draw, line, font)
        line_x = x if align == "left" else x + (width - line_width) // 2
        draw.text(
            (line_x + 4, y + 5),
            line,
            font=font,
            fill=palette["shadow"],
            stroke_width=7,
            stroke_fill=palette["shadow"],
        )
        draw.text(
            (line_x, y),
            line,
            font=font,
            fill=palette["text"],
            stroke_width=2,
            stroke_fill=palette["shadow"],
        )
        y += line_height
    return y


def draw_footer(draw, analysis, palette):
    elements = analysis.get("key_elements") or []
    label = " / ".join(str(item) for item in elements[:3])
    if not label:
        label = analysis.get("content_summary", "")
    label = label[:42]
    if not label:
        return
    font = load_font(34)
    x = SAFE
    y = CANVAS[1] - SAFE - 50
    pad_x = 22
    pad_y = 12
    box = draw.textbbox((0, 0), label, font=font)
    w = box[2] - box[0] + pad_x * 2
    h = box[3] - box[1] + pad_y * 2
    draw.rounded_rectangle((x, y, x + min(w, CANVAS[0] - SAFE * 2), y + h), radius=18, fill=(0, 0, 0, 150))
    draw.text((x + pad_x, y + pad_y - 3), label, font=font, fill=palette["accent2"])


def add_overlay(base, palette):
    overlay = Image.new("RGBA", CANVAS, palette["overlay"])
    return Image.alpha_composite(base.convert("RGBA"), overlay)


def apply_gradient(canvas, top_alpha, bottom_alpha):
    overlay = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    for y in range(CANVAS[1]):
        t = y / max(CANVAS[1] - 1, 1)
        alpha = int(top_alpha * (1 - t) + bottom_alpha * t)
        draw.line((0, y, CANVAS[0], y), fill=(0, 0, 0, alpha))
    return Image.alpha_composite(canvas, overlay)


def make_info_heavy(frame, title, analysis):
    palette = PALETTES["info-heavy"]
    base = cover_crop(frame).filter(ImageFilter.GaussianBlur(8))
    canvas = add_overlay(base, palette)
    canvas = apply_gradient(canvas, 90, 170)
    draw = ImageDraw.Draw(canvas, "RGBA")

    panel = (SAFE - 18, 170, CANVAS[0] - SAFE + 18, 720)
    draw.rounded_rectangle(panel, radius=34, fill=(0, 0, 0, 142), outline=palette["accent"] + (230,), width=5)
    draw.rectangle((SAFE, 202, SAFE + 132, 218), fill=palette["accent"] + (255,))
    draw_text_block(draw, title, (SAFE + 16, 250), CANVAS[0] - SAFE * 2 - 32, 118, 3, palette)
    draw_footer(draw, analysis, palette)
    return canvas.convert("RGB")


def make_visual_heavy(frame, title, analysis):
    palette = PALETTES["visual-heavy"]
    base = cover_crop(frame)
    canvas = add_overlay(base, palette)
    canvas = apply_gradient(canvas, 20, 190)
    draw = ImageDraw.Draw(canvas, "RGBA")

    y = 1040
    draw.rounded_rectangle((SAFE, y - 28, CANVAS[0] - SAFE, CANVAS[1] - SAFE), radius=28, fill=(0, 0, 0, 118))
    draw_text_block(draw, title, (SAFE + 26, y + 16), CANVAS[0] - SAFE * 2 - 52, 82, 2, palette, align="center")
    draw.rectangle((CANVAS[0] - SAFE - 140, y - 56, CANVAS[0] - SAFE, y - 44), fill=palette["accent"] + (255,))
    return canvas.convert("RGB")


def make_balanced(frame, title, analysis):
    palette = PALETTES["balanced"]
    base = cover_crop(frame)
    blurred = base.filter(ImageFilter.GaussianBlur(14))
    canvas = add_overlay(blurred, palette)
    sharp = base.resize((840, 1120), Image.Resampling.LANCZOS)
    canvas.alpha_composite(sharp.convert("RGBA"), (120, 92))
    canvas = apply_gradient(canvas, 70, 120)
    draw = ImageDraw.Draw(canvas, "RGBA")

    draw.rounded_rectangle((82, 82, 998, 1272), radius=36, outline=(255, 255, 255, 95), width=4)
    draw.rectangle((SAFE, 920, SAFE + 150, 936), fill=palette["accent"] + (255,))
    draw_text_block(draw, title, (SAFE, 956), CANVAS[0] - SAFE * 2, 96, 2, palette)
    draw_footer(draw, analysis, palette)
    return canvas.convert("RGB")


def pick_frame(workdir, analysis):
    recommended = analysis.get("recommended_frame")
    candidates = []
    if recommended:
        candidates.append(Path(recommended))
        candidates.append(workdir / recommended)
    index_path = workdir / "frames" / "index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
        frames = index.get("frames", [])
        if frames:
            middle = frames[len(frames) // 2].get("path")
            if middle:
                candidates.append(Path(middle))
    candidates.extend(sorted((workdir / "frames").glob("frame_*.jpg")))

    for candidate in candidates:
        candidate = candidate.expanduser()
        if not candidate.is_absolute():
            candidate = workdir / candidate
        if candidate.exists():
            return Image.open(candidate)
    raise SystemExit(f"No extracted frames found in {workdir / 'frames'}")


def main():
    parser = argparse.ArgumentParser(description="Render three 3:4 social cover variants.")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--title-file", required=True)
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    workdir = Path(args.workdir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    title = Path(args.title_file).expanduser().read_text(encoding="utf-8").strip()
    if not title:
        raise SystemExit("Title file is empty.")
    analysis = json.loads(Path(args.analysis).expanduser().read_text(encoding="utf-8"))
    frame = pick_frame(workdir, analysis)

    variants = {
        "info-heavy": make_info_heavy(frame, title, analysis),
        "visual-heavy": make_visual_heavy(frame, title, analysis),
        "balanced": make_balanced(frame, title, analysis),
    }
    for name, image in variants.items():
        image.save(output_dir / f"{name}.jpg", quality=94, subsampling=0)


if __name__ == "__main__":
    main()
