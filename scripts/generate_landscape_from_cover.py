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


CANVAS = (1440, 1080)


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


def image_data_url(image):
    buffer = BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=92, subsampling=0)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def data_url(path):
    path = Path(path).expanduser().resolve()
    return image_data_url(Image.open(path))


def contain(image, box):
    image = image.convert("RGB")
    width, height = box
    scale = min(width / image.width, height / image.height)
    size = (int(image.width * scale), int(image.height * scale))
    return image.resize(size, Image.Resampling.LANCZOS)


def reference_board_data_url(cover_path, layout_reference_path):
    cover = Image.open(cover_path)
    layout_reference = Image.open(layout_reference_path)
    board = Image.new("RGB", (2200, 1200), (8, 12, 18))

    cover_image = contain(cover, (760, 1040))
    cover_x = 60 + (760 - cover_image.width) // 2
    cover_y = 80 + (1040 - cover_image.height) // 2
    board.paste(cover_image, (cover_x, cover_y))

    layout_image = contain(layout_reference, (1280, 1040))
    layout_x = 860 + (1280 - layout_image.width) // 2
    layout_y = 80 + (1040 - layout_image.height) // 2
    board.paste(layout_image, (layout_x, layout_y))

    return image_data_url(board)


def is_health_landscape_context(*parts):
    text = " ".join(str(part or "") for part in parts).lower()
    tokens = (
        "睡眠",
        "睡少",
        "睡多",
        "熬夜",
        "失眠",
        "心电",
        "心脏",
        "闹钟",
        "健康",
        "高血压",
        "冠心病",
        "sleep",
        "insomnia",
    )
    return any(token in text for token in tokens)


def is_gold_landscape_context(*parts):
    text = " ".join(str(part or "") for part in parts).lower()
    tokens = (
        "黄金",
        "金条",
        "金币",
        "金库",
        "硬通货",
        "信用锚",
        "央行",
        "储备",
        "财富",
        "货币",
        "gold",
        "central bank",
    )
    return any(token in text for token in tokens)


def build_prompt(title, subtitle, source_variant, extra, layout, has_layout_reference, subject_description, style_description):
    is_health = is_health_landscape_context(title, subtitle, source_variant, extra, subject_description, style_description)
    is_gold = is_gold_landscape_context(title, subtitle, source_variant, extra, subject_description, style_description)
    reference_rules = (
        "参考图是一张左右拼接的参考板：左侧是必须继承的 3:4 选中封面，右侧是横版优秀案例。"
        "左侧决定核心元素、主视觉、色彩、暗部氛围、字体字效和整体质感；右侧只用于学习横版排版骨架：超大标题、清晰副标题标签、40-60% 主体锚点、横向延展背景。"
        "不要照搬右侧案例的人物、吉祥物、红色配色或具体文字，除非左侧选中封面本身也有这些元素。"
    )
    if not has_layout_reference:
        reference_rules = "参考图只用于提取视觉资产和风格，不要继承它的竖版构图。"

    if is_health:
        layout_rules = {
            "title-left-hero-right": (
                "采用真正的横版健康科普缩略图排版：左侧 45% 是大标题区，右侧 45% 是睡眠风险主视觉区。"
                "主标题必须非常大，作为第一视觉焦点，分成 1-2 行横排；副标题紧贴主标题下方。"
                "右侧主视觉使用暗夜床铺、闹钟、心电线、心脏警示或睡眠时长标识，不能使用办公数码界面。"
            ),
            "center-hero-left-title": (
                "采用横版健康科普主视觉排版：左侧大标题，中央偏右是暗夜睡眠场景和红色心电警示，背景是卧室空间横向延展。"
                "主标题要比竖版参考图更大，但必须保留安全边距。"
            ),
            "reference-mega-title": (
                "采用优秀横版封面的骨架重新构图：顶部或左上 25-32% 画面给超大主标题，"
                "主标题整体横跨画布 70-90% 宽度，字高约占画布高度 18-24%，远看必须一眼读清。"
                "主标题即使很大也必须留出安全边距：距离上边和左边至少 5-7% 画布，不要贴边、切边或顶到画布边缘。"
                "副标题做成明显的横向标签、胶囊或短横条，放在主标题下方，不能是角落小字。"
                "主视觉锚点占 40-60% 画面，放在中下或右侧前景，用床铺、闹钟、红色心电线、心脏警示形成单一睡眠健康主体。"
                "背景只允许暗夜卧室、窗帘、床头柜、睡眠波形、不可读医学风险卡片和柔和警示光，从左到右铺开。"
            ),
        }[layout]
    elif is_gold:
        layout_rules = {
            "title-left-hero-right": (
                "采用真正的横版财经知识缩略图排版：左侧 45% 是大标题区，右侧 45% 是黄金资产主视觉区。"
                "主标题必须非常大，作为第一视觉焦点，分成 1-2 行横排；标题整体必须完整放在画布内，左边距至少 90px，上边距至少 70px，右侧也要留安全边距。"
                "副标题紧贴主标题下方，做成黑金或琥珀金胶囊标签，标签也必须完整放在画布内。"
                "右侧主视觉使用金条堆、金币、央行金库门、信用锚符号和全球储备光线，不能出现无关软件截图感。"
            ),
            "center-hero-left-title": (
                "采用横版财经纪录片主视觉排版：左侧大标题，中央偏右是金条堆、金库门和信用锚符号，背景是深色金库空间横向延展。"
                "主标题要比竖版参考图更适合横版阅读，但必须保留安全边距，所有文字都不能贴边、切边或被主体遮挡。"
            ),
            "reference-mega-title": (
                "采用优秀横版封面的骨架重新构图：顶部或左上 25-34% 画面给超大主标题，"
                "主标题整体横跨画布 60-78% 宽度，字高约占画布高度 17-22%，远看必须一眼读清。"
                "主标题即使很大也必须留出安全边距：距离上边和左边至少 7-9% 画布，不要贴边、切边或顶到画布边缘。"
                "标题的每一个字都必须完整可见，不能有任何笔画超出画布。"
                "副标题做成明显的横向黑金胶囊、琥珀金铭牌或短横条，放在主标题下方，不能是角落小字。"
                "主视觉锚点占 40-58% 画面，放在中右或下方前景，用 999 金条、金币、金库门、信用锚符号和全球货币弧线形成单一黄金财经主体。"
                "背景只允许深黑金库、暗色世界地图、央行储备空间、金属反射、暖金体积光和不可读的储备比例图形，从左到右铺开。"
            ),
        }[layout]
    else:
        layout_rules = {
            "title-left-hero-right": (
                "采用真正的横版缩略图排版：左侧 45% 是大标题区，右侧 45% 是主视觉区。"
                "主标题必须非常大，作为第一视觉焦点，分成 1-2 行横排，占左侧标题区的大部分高度；"
                "副标题紧贴主标题下方，比主标题小但仍清楚。"
                "红色机械钳爪放在右侧，体积大、靠近镜头、有压迫感，不能被标题压小。"
            ),
            "center-hero-left-title": (
                "采用横版发布会主视觉排版：左侧大标题，中央偏右是巨大红色机械钳爪，背景 UI 向左右延展。"
                "主标题要比竖版参考图更大，不要放在底部小字区。"
            ),
            "reference-mega-title": (
                "采用优秀横版封面的骨架重新构图：顶部或左上 25-32% 画面给超大主标题，"
                "主标题整体横跨画布 70-95% 宽度，字高约占画布高度 18-26%，远看必须一眼读清。"
                "主标题即使很大也必须留出安全边距：距离上边和左边至少 5-7% 画布，不要贴边、切边或顶到画布边缘。"
                "副标题做成明显的横向标签、胶囊或短横条，放在主标题下方或右侧中部，不能是角落小字。"
                "主视觉锚点占 40-60% 画面，放在中右或下方前景，可以轻微压住背景 UI，但不能挡住主标题。"
                "背景 UI、节点、代码面板只作为暗部层次，从左到右铺开，形成横版封面的宽阔感。"
            ),
        }[layout]
    identity_rules = (
        subject_description
        or "保留左侧选中封面的核心识别元素：主视觉主体、人物或产品、主要符号、标题字效、背景信息层次。"
    )
    style_rules = (
        style_description
        or "延续选中封面的视觉风格：深色高级底色、清晰轮廓光、科技信息层、强对比标题、少量高饱和强调色。"
    )
    base_prompt = (
        f"{reference_rules}"
        "生成一张真正为横版视频缩略图设计的 4:3 横版封面，画布比例 4:3，横向构图，不是竖版封面横向外扩。"
        f"{identity_rules}"
        f"{style_rules}"
        f"{layout_rules}"
        "背景必须横向铺开，有从左到右的空间层次和光效动线；左侧文字区要有干净暗背景，右侧主体区要有细节和轮廓光。"
        f"文字必须由模型直接设计进画面，只出现这些文字：主标题「{title}」，副标题「{subtitle}」。"
        "标题完整、不贴边、不变形、不缩小成角落小字；主标题和副标题的字体质感、描边、阴影、色温要尽量接近选中 3:4 封面。"
        "横版缩略图远看也要先读到标题，但不能为了放大文字而牺牲安全边距或破坏与竖版的视觉系统一致性。"
        "如果标题和主体发生冲突，优先保证标题巨大且清晰，再调整主体位置。"
    )
    if is_health:
        return (
            f"{base_prompt}"
            "整体像高级健康科普栏目横版封面，图文层级强、标题大、睡眠风险主体明确、暗夜卧室氛围真实。"
            "禁止竖版海报式居中小标题，禁止把原图简单拉宽，禁止只在四周补背景，禁止标题小于主视觉。"
            "不要生成二维码、水印、平台角标、假 logo、可识别真人、人脸、陌生主持人、办公数码界面、编程开发元素、金融行情元素、箭头贴纸、emoji；除标题和副标题外不要有可读小字。"
            f"参考图来源策略：{source_variant}。"
            f"{extra}"
        )
    if is_gold:
        return (
            f"{base_prompt}"
            "整体像高级财经知识栏目横版封面或商业纪录片海报，图文层级强、标题大、黄金资产主体明确、黑金财富质感高级克制。"
            "禁止竖版海报式居中小标题，禁止把原图简单拉宽，禁止只在四周补背景，禁止标题小于主视觉。"
            "不要生成二维码、水印、平台角标、假 logo、可识别真人、人脸、陌生主持人、廉价暴富贴纸、emoji；除标题和副标题外不要有可读小字。"
            f"参考图来源策略：{source_variant}。"
            f"{extra}"
        )
    return (
        f"{base_prompt}"
        "整体像高端 AI 产品发布会横版海报或 YouTube/B站横版科技封面，图文层级强、标题大、主体大、留白有控制。"
        "禁止竖版海报式居中小标题，禁止把原图简单拉宽，禁止只在四周补背景，禁止标题小于主视觉。"
        "不要生成二维码、水印、平台角标、假 logo、无关人物或陌生主持人、箭头贴纸、emoji；背景 UI 不要有可读小字。"
        f"参考图来源策略：{source_variant}。"
        f"{extra}"
    )


def call_image_api(prompt, reference_image):
    api_url = os.getenv("VCG_IMAGE_API_URL", "https://ark.cn-beijing.volces.com/api/v3/images/generations")
    api_key = os.getenv("VCG_IMAGE_API_KEY")
    model = os.getenv("VCG_IMAGE_MODEL", "doubao-seedream-5-0-260128")
    size = os.getenv("VCG_IMAGE_SIZE", "2K")
    reference_field = os.getenv("VCG_IMAGE_REFERENCE_FIELD", "reference_image")
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
        reference_field: reference_image,
    }
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
    parser = argparse.ArgumentParser(description="Generate a 4:3 landscape cover from a selected 3:4 cover.")
    parser.add_argument("--cover", required=True, help="Selected 3:4 cover image.")
    parser.add_argument("--output", required=True, help="Output 4:3 JPG path.")
    parser.add_argument("--prompt-output", help="Optional path to save the generated prompt JSON.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--subtitle", required=True)
    parser.add_argument("--source-variant", default="selected-3x4-cover")
    parser.add_argument("--layout", choices=["title-left-hero-right", "center-hero-left-title", "reference-mega-title"], default="title-left-hero-right")
    parser.add_argument("--layout-reference", help="Optional landscape reference image. It is used for layout only, while --cover remains the identity/style source.")
    parser.add_argument("--subject-description", default="", help="What identity/subject elements to preserve from the selected cover.")
    parser.add_argument("--style-description", default="", help="What style elements to preserve from the selected cover.")
    parser.add_argument("--extra", default="")
    args = parser.parse_args()

    cover_path = Path(args.cover).expanduser().resolve()
    if not cover_path.exists():
        raise SystemExit(f"Cover not found: {cover_path}")

    layout_reference_path = None
    if args.layout_reference:
        layout_reference_path = Path(args.layout_reference).expanduser().resolve()
        if not layout_reference_path.exists():
            raise SystemExit(f"Layout reference not found: {layout_reference_path}")

    prompt = build_prompt(
        args.title,
        args.subtitle,
        args.source_variant,
        args.extra,
        args.layout,
        bool(layout_reference_path),
        args.subject_description,
        args.style_description,
    )
    if args.prompt_output:
        prompt_output = Path(args.prompt_output).expanduser().resolve()
        prompt_output.parent.mkdir(parents=True, exist_ok=True)
        prompt_output.write_text(
            json.dumps({
                "source_cover": str(cover_path),
                "layout_reference": str(layout_reference_path) if layout_reference_path else None,
                "title": args.title,
                "subtitle": args.subtitle,
                "source_variant": args.source_variant,
                "layout": args.layout,
                "subject_description": args.subject_description,
                "style_description": args.style_description,
                "prompt": prompt,
                "canvas": {"width": CANVAS[0], "height": CANVAS[1], "aspect": "4:3"},
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    reference_image = reference_board_data_url(cover_path, layout_reference_path) if layout_reference_path else data_url(cover_path)
    image = call_image_api(prompt, reference_image)
    image = cover_crop(image)

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, quality=94, subsampling=0)


if __name__ == "__main__":
    main()
