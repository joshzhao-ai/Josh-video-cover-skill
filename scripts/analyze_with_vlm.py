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
    max_side = int(os.getenv("VCG_VLM_MAX_IMAGE_SIDE", "1024"))
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=86, optimize=True)
    raw = buffer.getvalue()
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")


def pick_frames(frames_dir, max_frames):
    frames = sorted(Path(frames_dir).expanduser().glob("frame_*.jpg"))
    if not frames:
        raise SystemExit(f"No frame_*.jpg files found in {frames_dir}")
    if len(frames) <= max_frames:
        return frames
    step = (len(frames) - 1) / (max_frames - 1)
    indexes = [round(i * step) for i in range(max_frames)]
    return [frames[i] for i in indexes]


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
    if "analysis" in response_json:
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


def normalize(payload, frames):
    if "analysis" in payload:
        analysis = payload["analysis"]
        titles = payload.get("titles", [])
        subtitles = payload.get("subtitles", [])
        title_candidates = payload.get("title_candidates", [])
    else:
        analysis = payload
        titles = payload.get("titles", [])
        subtitles = payload.get("subtitles", [])
        title_candidates = payload.get("title_candidates", [])

    if isinstance(titles, dict):
        titles = titles.get("titles", [])
    if not titles and isinstance(title_candidates, list):
        for item in title_candidates:
            if isinstance(item, dict):
                value = item.get("title")
            else:
                value = item
            if value:
                titles.append(value)
    titles = [str(item).strip() for item in titles if str(item).strip()][:3]
    if len(titles) < 3:
        titles.extend(["别急着上手", "真实体验", "踩坑实测"][len(titles):])
    if isinstance(subtitles, dict):
        subtitles = subtitles.get("subtitles", [])
    subtitles = [str(item).strip() for item in subtitles if str(item).strip()][:3]

    default_frame = f"frames/{frames[len(frames) // 2].name}"
    analysis = {
        "video_type": analysis.get("video_type", "info_expression"),
        "subject_strategy": analysis.get("subject_strategy", "screen-or-product"),
        "industry": analysis.get("industry", "科技知识"),
        "cover_archetype": analysis.get("cover_archetype", "tech-knowledge"),
        "person_policy": analysis.get("person_policy", "do-not-invent-person"),
        "needs_real_person_asset": bool(analysis.get("needs_real_person_asset", False)),
        "key_elements": analysis.get("key_elements", [])[:5],
        "mood": analysis.get("mood", ""),
        "content_summary": analysis.get("content_summary", ""),
        "hook_summary": analysis.get("hook_summary", ""),
        "title_strategy": analysis.get("title_strategy", ""),
        "recommended_frame": analysis.get("recommended_frame", default_frame),
    }
    result = {"titles": titles}
    if subtitles:
        result["subtitles"] = subtitles
    if title_candidates:
        result["title_candidates"] = title_candidates
    return analysis, result


def main():
    parser = argparse.ArgumentParser(description="Analyze extracted video frames with a multimodal API.")
    parser.add_argument("--frames-dir", required=True)
    parser.add_argument("--analysis-output", required=True)
    parser.add_argument("--titles-output", required=True)
    parser.add_argument("--language", default="zh")
    parser.add_argument("--max-frames", type=int, default=12)
    parser.add_argument("--provider", choices=["auto", "openai", "doubao"], default="auto")
    args = parser.parse_args()

    api_url = os.getenv("VCG_VLM_API_URL", "https://ark.cn-beijing.volces.com/api/v3/responses")
    api_key = os.getenv("VCG_VLM_API_KEY")
    model = os.getenv("VCG_VLM_MODEL", "doubao-seed-2-0-pro-260215")
    if not api_url or not api_key or not model:
        raise SystemExit("Set VCG_VLM_API_KEY. Optionally set VCG_VLM_API_URL and VCG_VLM_MODEL.")

    frames = pick_frames(args.frames_dir, args.max_frames)
    language_hint = "Chinese" if args.language.startswith("zh") else "English"
    prompt = f"""
You are an expert Douyin tech-knowledge cover editor and title strategist.
Analyze frames from a short video to design social cover images.
Return JSON only. Use {language_hint} for title candidates.

Benchmark rules for Chinese tech-knowledge covers:
- A cover title must create a click hook, not merely summarize the video.
- Prefer industry-specific hooks: pain point, risk, reversal, real test result, mistake, before/after, strong curiosity.
- For AI/dev-tool videos, good hooks include real-use pain, account risk, workflow change, time/result contrast, and "is it worth using".
- Primary cover title should be 4-10 Chinese characters. Keep each visual text line short, ideally no more than 5 Chinese characters.
- Cover copy and the original video title should not be identical; it needs information gain.
- If a person appears in the video, do not invent a new person. Set person_policy to "real-person-only" and needs_real_person_asset to true when a person should appear on the cover.
- If no reliable real-person asset is available, recommend a no-person cover using product/UI/symbolic visuals instead.

Classify the video into one of:
- info_expression: software demos, UI, charts, product/tool explanation
- object_operation: hands, tools, repairs, DIY, unboxing, cooking, craft
- lifestyle_scene: vlog, street, person, travel, beauty, food, cinematic ambience

Return exactly:
{{
  "analysis": {{
    "video_type": "info_expression | object_operation | lifestyle_scene",
    "subject_strategy": "screen-or-product | hands-tools-object | real-person-from-frame | no-person-symbolic",
    "industry": "specific vertical, e.g. AI开发工具/编程效率/科技知识",
    "cover_archetype": "AI教程型 | 产品展示型 | 无博主符号型 | 有博主实测型",
    "person_policy": "do-not-invent-person | real-person-only | no-person-needed",
    "needs_real_person_asset": true,
    "key_elements": ["3 to 5 concrete visual/product elements"],
    "mood": "one sentence cover mood",
    "content_summary": "one sentence summary",
    "hook_summary": "the strongest click hook in one sentence",
    "title_strategy": "why the title candidates fit this industry",
    "recommended_frame": "frames/frame_XX.jpg"
  }},
  "titles": ["3 punchy cover titles, 4-10 Chinese chars or 2-5 English words"],
  "subtitles": ["3 short explanatory subtitles"],
  "title_candidates": [
    {{"title": "candidate", "subtitle": "candidate", "hook_type": "risk/reversal/result/pain/curiosity", "reason": "short reason"}}
  ]
}}

Bad title examples: "Claude使用实测", "AI工具介绍", "真实感受分享".
Better title examples for an AI dev tool experience video: "别急着上手", "两周后真相", "用到被封号", "真的省时间?", "踩坑后再说".
Do not invent a presenter. Do not recommend generic stock-photo imagery.
""".strip()

    provider = args.provider
    if provider == "auto":
        provider = "doubao" if "/responses" in api_url else "openai"

    if provider == "doubao":
        content = [{"type": "input_image", "image_url": data_url(frame)} for frame in frames]
        content.append({"type": "input_text", "text": prompt})
        body = {
            "model": model,
            "input": [{"role": "user", "content": content}],
        }
    else:
        content = [{"type": "text", "text": prompt}]
        for frame in frames:
            content.append({"type": "image_url", "image_url": {"url": data_url(frame)}})
        body = {
            "model": model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": content}],
        }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    response = requests.post(api_url, headers=headers, json=body, timeout=120)
    response.raise_for_status()
    payload = response_content(response.json())
    analysis, titles = normalize(payload, frames)

    Path(args.analysis_output).expanduser().write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    Path(args.titles_output).expanduser().write_text(
        json.dumps(titles, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
