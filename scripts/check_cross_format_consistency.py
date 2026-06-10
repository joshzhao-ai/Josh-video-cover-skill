#!/usr/bin/env python3
import argparse
import base64
import json
import os
import re
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image


def data_url(path):
    max_side = int(os.getenv("VCG_VLM_MAX_IMAGE_SIDE", "1280"))
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=88, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def extract_json(value):
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        raise ValueError("VLM response is neither a JSON object nor a string.")
    text = value.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    return json.loads(text)


def response_content(response_json):
    if "passed" in response_json or "scores" in response_json:
        return response_json
    if "output_text" in response_json:
        return extract_json(response_json["output_text"])
    try:
        chunks = []
        for item in response_json.get("output", []):
            for content in item.get("content", []):
                text = content.get("text") or content.get("output_text")
                if text:
                    chunks.append(text)
        if chunks:
            return extract_json("\n".join(chunks))
    except AttributeError:
        pass
    try:
        return extract_json(response_json["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError):
        return extract_json(response_json)


def clamp_score(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(10, round(value, 1)))


def normalize(payload, portrait, landscape, title, subtitle):
    scores = payload.get("scores", {}) if isinstance(payload, dict) else {}
    normalized_scores = {
        "title_consistency": clamp_score(scores.get("title_consistency")),
        "subtitle_consistency": clamp_score(scores.get("subtitle_consistency")),
        "subject_consistency": clamp_score(scores.get("subject_consistency")),
        "style_consistency": clamp_score(scores.get("style_consistency")),
        "landscape_composition": clamp_score(scores.get("landscape_composition")),
        "thumbnail_legibility": clamp_score(scores.get("thumbnail_legibility")),
    }
    overall = payload.get("overall_score")
    if overall is None:
        weights = {
            "title_consistency": 0.2,
            "subtitle_consistency": 0.1,
            "subject_consistency": 0.2,
            "style_consistency": 0.15,
            "landscape_composition": 0.2,
            "thumbnail_legibility": 0.15,
        }
        overall = sum(normalized_scores[key] * weight for key, weight in weights.items())
    overall = clamp_score(overall)
    critical_issues = payload.get("critical_issues") or []
    issues = payload.get("issues") or []
    passed = bool(payload.get("passed", overall >= 7 and not critical_issues))
    if overall < 7 or critical_issues:
        passed = False
    return {
        "passed": passed,
        "overall_score": overall,
        "scores": normalized_scores,
        "critical_issues": critical_issues,
        "issues": issues,
        "detected": payload.get("detected", {}),
        "recommendation": payload.get("recommendation", ""),
        "expected": {
            "title": title,
            "subtitle": subtitle,
            "portrait": str(portrait),
            "landscape": str(landscape),
        },
    }


def call_vlm(portrait, landscape, title, subtitle):
    api_url = os.getenv("VCG_VLM_API_URL", "https://ark.cn-beijing.volces.com/api/v3/responses")
    api_key = os.getenv("VCG_VLM_API_KEY")
    model = os.getenv("VCG_VLM_MODEL", "doubao-seed-2-0-pro-260215")
    if not api_url or not api_key or not model:
        raise SystemExit("Set VCG_VLM_API_KEY. Optionally set VCG_VLM_API_URL and VCG_VLM_MODEL.")

    prompt = f"""
你是短视频封面质检员。请比较两张同一视频的封面：
- 图1是 3:4 竖版封面。
- 图2是 4:3 横版封面。

目标：判断横版是否与竖版保持同一内容身份，同时横版本身是否像真正的横版封面，而不是竖版硬扩。

期望主标题：{title}
期望副标题：{subtitle}

请严格检查：
1. 主标题是否一致、清晰、没有明显错字、乱码、裁切。
2. 副标题是否一致或语义一致，不能乱变。
3. 主体/产品/人物/符号是否保持同一内容身份；真人视频尤其不能从一个人变成另一个人。
   一致性必须以图1这张已选中的 3:4 封面为准，而不是只看视频主题是否相近。
   对非真人的符号型/产品型科技封面，允许横版为了构图把主体姿态、视角、体量重新设计，
   但必须仍然能读出来自图1的同一视觉资产家族：相同核心符号、相近颜色材质、相近背景系统。
   例如图1是红色机械钳爪，图2重构成更有压迫感的红色机械臂钳爪，且仍保留深蓝科技背景和标题风格，可以视为一致。
   但如果图2变成无关产品、人物、吉祥物、圆环装置，或者图1的关键识别线索基本消失，就应判为不一致。
4. 色彩、光效、材质、背景元素是否像同一个封面系统。
   字体风格、描边、阴影、色温和整体标题气质也要像同一个系统；如果横版字体变得普通、廉价或与竖版明显脱节，要扣分。
5. 横版构图是否合理：标题够大，主体有 40-60% 锚点，背景横向展开，不像竖版外扩。
   大标题不能贴边、切边、顶边或挤到画布边缘；安全边距不足是横版构图问题。
6. 信息流缩略图远看是否能先读到标题。

返回 JSON，不要解释，不要 Markdown：
{{
  "passed": true,
  "overall_score": 0-10,
  "scores": {{
    "title_consistency": 0-10,
    "subtitle_consistency": 0-10,
    "subject_consistency": 0-10,
    "style_consistency": 0-10,
    "landscape_composition": 0-10,
    "thumbnail_legibility": 0-10
  }},
  "critical_issues": ["致命问题列表，没有则空数组"],
  "issues": ["一般问题列表，没有则空数组"],
  "detected": {{
    "portrait_title": "你看到的竖版标题",
    "landscape_title": "你看到的横版标题",
    "portrait_subject": "竖版主体",
    "landscape_subject": "横版主体"
  }},
  "recommendation": "下一步建议，一句话"
}}
""".strip()

    provider = "doubao" if "/responses" in api_url else "openai"
    if provider == "doubao":
        body = {
            "model": model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": data_url(portrait)},
                        {"type": "input_image", "image_url": data_url(landscape)},
                    ],
                }
            ],
        }
    else:
        body = {
            "model": model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url(portrait)}},
                        {"type": "image_url", "image_url": {"url": data_url(landscape)}},
                    ],
                }
            ],
        }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    response = requests.post(api_url, headers=headers, json=body, timeout=160)
    response.raise_for_status()
    return response_content(response.json())


def main():
    parser = argparse.ArgumentParser(description="Check visual and text consistency between 3:4 and 4:3 cover outputs.")
    parser.add_argument("--portrait", required=True, help="Selected 3:4 cover image.")
    parser.add_argument("--landscape", required=True, help="Generated 4:3 landscape cover image.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--subtitle", default="")
    args = parser.parse_args()

    portrait = Path(args.portrait).expanduser().resolve()
    landscape = Path(args.landscape).expanduser().resolve()
    if not portrait.exists():
        raise SystemExit(f"Portrait cover not found: {portrait}")
    if not landscape.exists():
        raise SystemExit(f"Landscape cover not found: {landscape}")

    payload = call_vlm(portrait, landscape, args.title, args.subtitle)
    report = normalize(payload, portrait, landscape, args.title, args.subtitle)
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
