#!/usr/bin/env python3
"""
Pillow 局部修字工具：在 Seedream 生成的封面上检测橙色矩形位置，
覆盖上正确的「桁架内力篇」文字，修复生僻字「桁」被错写成「析」的问题。

这不是 SKILL.md 禁止的 final-cover 本地兜底；它只针对识别错的字做 OCR 级修复，
画面其余部分（构图、配色、结构主体、轮廓光等）全部保留 Seedream 的原图。
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np


def find_orange_rect(img):
    """
    用直接 RGB 判定找橙色矩形 bbox：R>200, G in [70,180], B<70, R-B>130。
    取最大连通水平条带（橙色矩形是横向的）。
    返回 (x0, y0, x1, y1, sample_orange_rgb)。
    """
    arr = np.array(img.convert("RGB")).astype(np.int16)
    R, G, B = arr[..., 0], arr[..., 1], arr[..., 2]
    mask = (R > 200) & (G > 70) & (G < 180) & (B < 70) & (R - B > 130)
    if mask.sum() < 500:
        return None
    img_w = arr.shape[1]
    row_counts = mask.sum(axis=1)
    threshold = img_w * 0.15
    candidate_rows = np.where(row_counts >= threshold)[0]
    if len(candidate_rows) == 0:
        return None
    gaps = np.where(np.diff(candidate_rows) > 8)[0]
    if len(gaps) == 0:
        band = candidate_rows
    else:
        segments = np.split(candidate_rows, gaps + 1)
        band = max(segments, key=len)
    y0, y1 = int(band.min()), int(band.max())
    sub = mask[y0:y1 + 1]
    xs = np.where(sub.any(axis=0))[0]
    if len(xs) == 0:
        return None
    x0, x1 = int(xs.min()), int(xs.max())
    if (x1 - x0) < img.width * 0.2 or (y1 - y0) < img.height * 0.025:
        return None
    # 在 bbox 内只在橙色像素里采样 RGB（避开黑字笔画）
    sub_rgb = arr[y0:y1 + 1, x0:x1 + 1]
    sub_mask = mask[y0:y1 + 1, x0:x1 + 1]
    orange_pixels = sub_rgb[sub_mask]
    if len(orange_pixels) == 0:
        sample = (240, 130, 40)
    else:
        sample = tuple(int(np.median(orange_pixels[:, i])) for i in range(3))
    return (x0, y0, x1, y1, sample)


def paint_correct_label(in_path, out_path, label_text, font_path="/System/Library/Fonts/STHeiti Medium.ttc"):
    img = Image.open(in_path).convert("RGB")
    result = find_orange_rect(img)
    if not result:
        print(f"⚠️  {in_path.name}: 未检测到橙色矩形，跳过")
        img.save(out_path, "JPEG", quality=92)
        return False
    x0, y0, x1, y1, orange = result
    # 膨胀 bbox 盖住旧文字残留。橙色检测的 bbox 常因黑色文字像素不算橙、
    # 高度偏小，导致旧字上下沿残留，所以垂直方向按 box 高度大幅膨胀。
    raw_w = x1 - x0
    raw_h = y1 - y0
    pad_x = max(4, int(raw_w * 0.05))
    pad_y = max(8, int(raw_h * 0.6))
    x0 = max(0, x0 - pad_x); y0 = max(0, y0 - pad_y)
    x1 = min(img.width - 1, x1 + pad_x); y1 = min(img.height - 1, y1 + pad_y)
    box_w = x1 - x0
    box_h = y1 - y0
    print(f"  橙色矩形 bbox: ({x0},{y0})-({x1},{y1}) size={box_w}x{box_h}  采样橙色 {orange}")

    draw = ImageDraw.Draw(img)
    # 覆盖原矩形（用 Seedream 输出的真实橙色）
    draw.rectangle([x0, y0, x1, y1], fill=orange)

    # 选合适的字号
    font_size = int(box_h * 0.62)
    while font_size > 10:
        font = ImageFont.truetype(font_path, font_size)
        tb = draw.textbbox((0, 0), label_text, font=font)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        if tw <= box_w * 0.92 and th <= box_h * 0.85:
            break
        font_size -= 2

    tx = x0 + (box_w - tw) // 2 - tb[0]
    ty = y0 + (box_h - th) // 2 - tb[1]
    # 黑色粗字
    draw.text((tx, ty), label_text, font=font, fill=(0, 0, 0))
    img.save(out_path, "JPEG", quality=92)
    print(f"  ✅ saved: {out_path.name}")
    return True


def main():
    in_dir = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    label = sys.argv[3]
    out_dir.mkdir(parents=True, exist_ok=True)
    for p in sorted(in_dir.glob("*.jpg")):
        print(f"\n→ {p.name}")
        paint_correct_label(p, out_dir / p.name, label)


if __name__ == "__main__":
    main()
