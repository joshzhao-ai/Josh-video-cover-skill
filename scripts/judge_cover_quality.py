#!/usr/bin/env python3
"""
单张 3:4 封面的 VLM 质量 judge。

输出与 check_cross_format_consistency.py 同风格的评分 JSON，但维度针对单张封面，
并直接对应老板亲点的两个 bug：标题语义理解错误、文字排版/错字。

错字检测用双保险：VLM 读出封面实际文字（detected_title）+ 程序侧归一化字符串比对
（title_match），命中差异时强制注入 critical，不完全依赖 VLM 打分。

可复用部分（data_url / extract_json / response_content / clamp_score / call_vlm 骨架 /
normalize 模板）从 scripts/check_cross_format_consistency.py 复制而来，保持各脚本自带一份
工具函数的现有风格（不跨脚本 import），降低耦合。
"""
import argparse
import base64
import json
import os
import re
import time
import unicodedata
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
REFERENCES_DIR = SCRIPT_DIR.parent / "references"

# judge 维度权重（与 references/tech_cover_checklist.md 的映射表一致）。
DIMENSION_WEIGHTS = {
    "title_text_correctness": 0.20,
    "title_semantic_match": 0.20,
    "text_layout": 0.15,
    "vertical_style_match": 0.15,
    "info_hierarchy": 0.10,
    "thumbnail_legibility": 0.10,
    "aesthetics": 0.10,
}

# 有官方参考封面时：主体准确性 + 官方核心策略继承占大头。
# 这是回应「judge 10/10 不代表接近官方」——没有官方对标，judge 只会自嗨。
DIMENSION_WEIGHTS_WITH_REF = {
    "title_text_correctness": 0.12,
    "title_semantic_match": 0.12,
    "text_layout": 0.08,
    "vertical_style_match": 0.08,
    "info_hierarchy": 0.06,
    "thumbnail_legibility": 0.07,
    "aesthetics": 0.10,
    "subject_accuracy": 0.20,        # 主体是否准确（具体产品 vs 泛化/无关品牌）
    "reference_inheritance": 0.17,   # 是否继承官方核心视觉策略
}


# ---------- 复用自 check_cross_format_consistency.py ----------
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


# ---------- 新写 ----------
CHECKLIST_FILES = {
    "tech": "tech_cover_checklist.md",
    "digital_review": "digital_review_cover_checklist.md",
    "academic": "academic_minimalist_poster.md",
    "food": "food_documentary_poster.md",
}


def load_checklist(vertical):
    """读垂类 checklist 注入 judge prompt。先查别名映射，再退化到 {vertical}_cover_checklist.md，最后通用 fallback。"""
    candidates = []
    if vertical in CHECKLIST_FILES:
        candidates.append(REFERENCES_DIR / CHECKLIST_FILES[vertical])
    candidates.append(REFERENCES_DIR / f"{vertical}_cover_checklist.md")
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
    return (
        "（未找到该垂类专属 checklist，按通用短视频封面标准评估：标题文字正确、标题语义与视频内容一致、"
        "排版端正清晰、视觉层级 title>subject>background、深色高对比、主体具体、无水印/二维码/假 logo/假人脸。）"
    )


def normalize_text(s):
    """归一化：全角转半角、去空白、去常见中英文标点，转小写。用于标题字符串比对。"""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[，。、；：！？,.;:!?\"'`「」『』（）()\[\]【】<>《》~～\-—_…·|/\\]", "", s)
    return s.lower()


def levenshtein(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def title_match(expected, detected):
    """程序侧标题比对。归一化后做编辑距离，捕捉错字/形近字。

    子串包含豁免：多层文字封面里 VLM 常把 kicker/系列标签连读进主标题
    （如期望「结构力学」、读到「这样的结构力学你喜欢吗？」），或只读到核心标题。
    只要期望文字完整出现在检测文字里（或反之），核心标题就是对的，不算错字。
    真错字（如「桁架内力篇」→「析架内力篇」）不构成子串关系，仍会被编辑距离抓到。
    """
    e = normalize_text(expected)
    d = normalize_text(detected)
    if not d:
        return {
            "expected": expected, "detected": detected, "exact_match": False,
            "normalized_distance": len(e), "has_typo": False, "unreadable": True, "contained": False,
        }
    if e and (e in d or d in e):
        return {
            "expected": expected, "detected": detected, "exact_match": (e == d),
            "normalized_distance": abs(len(e) - len(d)), "has_typo": False, "unreadable": False, "contained": True,
        }
    dist = levenshtein(e, d)
    return {
        "expected": expected, "detected": detected, "exact_match": (dist == 0),
        "normalized_distance": dist, "has_typo": (dist != 0), "unreadable": False, "contained": False,
    }


def build_judge_prompt(analysis, title, subtitle, checklist_text, reference=None):
    summary = analysis.get("content_summary", "") or analysis.get("hook_summary", "")
    industry = analysis.get("industry", "")
    key_elements = "、".join(map(str, analysis.get("key_elements", []) or []))
    if reference:
        return f"""
你是抖音科技垂类封面的资深质检员。**图1 是 skill 生成的封面，图2 是同一视频的【官方优质封面】（标杆）。**
请严格质检图1，并重点判断它是否真正达到图2 的水准——不要因为图1"干净、字清楚"就给高分，
关键看它是否用对了主体、是否继承了官方的视觉策略和内容语境。

【视频真实内容】
- 内容摘要：{summary}
- 行业垂类：{industry}
- 关键元素：{key_elements}

【图1 期望的文字】主标题：{title}　副标题：{subtitle}

【科技垂类验收标准】
{checklist_text}

请完成：
1. 逐字读出图1 的主标题、副标题 → detected_title / detected_subtitle（一字不差，含错字）。
2. 读出图1 主体（detected.subject）和图2 官方主体（detected.official_subject）。
3. 按 9 个维度打 0-10 分。前 7 个是基础质检，后 2 个是【对标官方】（最重要）：
   - title_text_correctness: 主标题与期望逐字一致、无错字乱码裁切
   - title_semantic_match: 标题正确表达视频内容，非泛泛总结
   - text_layout: 排版端正、不挤压、不压主体、不贴边
   - vertical_style_match: 符合科技垂类视觉
   - info_hierarchy: 层级 title>subject>background 清晰、不杂
   - thumbnail_legibility: 缩略图标题可读
   - aesthetics: 整体美学
   - subject_accuracy（对标官方·关键）: 图1 主体是否和图2 一样【具体准确】。
     严格扣分：① 官方是具体产品（如 MediaTek 天玑芯片）而图1 用了泛化主体（一排泛芯片/泛设备）→ ≤4 分；
     ② 图1 混入无关/错误品牌符号（如该是天玑却出现 Apple logo）→ ≤3 分；③ 主体跑偏 → 低分。
   - reference_inheritance（对标官方·关键）: 图1 是否继承图2 的核心视觉策略——
     主体选择、构图逻辑、标题冲击力与面积、内容语境（如"选购指南"官方表达多款对比/选择关系，
     图1 若只做整齐产品陈列、丢失"怎么选"语境 → 低分）。图1 太像模板化 AI 干净图、缺官方真实封面设计感 → 低分。
4. critical_issues 必须包含（命中即写）：主体错误/泛化/无关品牌符号（subject_accuracy<5 时）、
   丢失官方核心策略或内容语境（reference_inheritance<5 时）、标题错字、排版崩。

返回 JSON，不要解释，不要 Markdown：
{{
  "detected_title": "", "detected_subtitle": "",
  "overall_score": 0-10,
  "scores": {{
    "title_text_correctness": 0-10, "title_semantic_match": 0-10, "text_layout": 0-10,
    "vertical_style_match": 0-10, "info_hierarchy": 0-10, "thumbnail_legibility": 0-10,
    "aesthetics": 0-10, "subject_accuracy": 0-10, "reference_inheritance": 0-10
  }},
  "critical_issues": [], "issues": [],
  "detected": {{ "subject": "图1的主体", "official_subject": "图2官方的主体", "reads_as_summary_not_hook": false }},
  "reference_gap": "图1 相比官方图2 最大的 1-2 个差距，具体一句话",
  "recommendation": "下一步建议，一句话"
}}
""".strip()
    return f"""
你是抖音科技垂类短视频封面的专业质检员。下面是一张 3:4 竖版封面，请严格质检。

【视频真实内容】（用于判断封面标题是否表达正确）
- 内容摘要：{summary}
- 行业垂类：{industry}
- 关键元素：{key_elements}

【这张封面期望的文字】
- 期望主标题：{title}
- 期望副标题：{subtitle}

【科技垂类验收标准】
{checklist_text}

请完成两件事：
1. 逐字读出封面上实际出现的主标题、副标题文字，一字不差照抄你看到的（包括任何错字/乱码），
   分别填到 detected_title / detected_subtitle。读不出就填空字符串。
2. 按下面 7 个维度各打 0-10 分，并对照验收标准列出 critical_issues（致命问题：错字/乱码、
   标题与视频内容不符、排版崩坏压字贴边、生成视频里不存在的假人脸）和 issues（一般问题）。

7 个打分维度：
- title_text_correctness: 封面主标题是否与期望主标题逐字一致、无错字乱码裁切
- title_semantic_match: 标题是否正确表达了上面的视频真实内容，不是牛头不对马嘴或泛泛总结
- text_layout: 文字排版是否端正、不挤压、不压住主体关键部位、断行可读、不贴边切边
- vertical_style_match: 是否符合科技垂类视觉（深色高对比、主色≤3、主体具体、无水印二维码假logo脏小字）
- info_hierarchy: 视觉层级 title>subject>background 是否清晰、核心元素是否≤5不杂乱
- thumbnail_legibility: 手机信息流缩略图尺寸下主标题是否仍清晰可读
- aesthetics: 整体美学观感

返回 JSON，不要解释，不要 Markdown：
{{
  "detected_title": "你逐字读到的封面主标题",
  "detected_subtitle": "你逐字读到的封面副标题",
  "overall_score": 0-10,
  "scores": {{
    "title_text_correctness": 0-10,
    "title_semantic_match": 0-10,
    "text_layout": 0-10,
    "vertical_style_match": 0-10,
    "info_hierarchy": 0-10,
    "thumbnail_legibility": 0-10,
    "aesthetics": 0-10
  }},
  "critical_issues": ["致命问题列表，没有则空数组"],
  "issues": ["一般问题列表，没有则空数组"],
  "detected": {{
    "subject": "你看到的主体是什么",
    "reads_as_summary_not_hook": false
  }},
  "recommendation": "下一步建议，一句话"
}}
""".strip()


def call_vlm(cover_path, prompt, reference=None, max_retries=3):
    api_url = os.getenv("VCG_VLM_API_URL", "https://ark.cn-beijing.volces.com/api/v3/responses")
    api_key = os.getenv("VCG_VLM_API_KEY")
    model = os.getenv("VCG_VLM_MODEL", "doubao-seed-2-0-pro-260215")
    if not api_key:
        raise SystemExit("Set VCG_VLM_API_KEY. Optionally set VCG_VLM_API_URL and VCG_VLM_MODEL.")

    provider = "doubao" if "/responses" in api_url else "openai"
    if provider == "doubao":
        content = [{"type": "input_text", "text": prompt},
                   {"type": "input_image", "image_url": data_url(cover_path)}]
        if reference:
            content.append({"type": "input_image", "image_url": data_url(reference)})
        body = {"model": model, "input": [{"role": "user", "content": content}]}
    else:
        content = [{"type": "text", "text": prompt},
                   {"type": "image_url", "image_url": {"url": data_url(cover_path)}}]
        if reference:
            content.append({"type": "image_url", "image_url": {"url": data_url(reference)}})
        body = {"model": model, "temperature": 0.1, "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": content}]}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    last_err = None
    for attempt in range(max_retries):
        try:
            response = requests.post(api_url, headers=headers, json=body, timeout=160)
            if response.status_code in (429, 500, 502, 503, 504):
                last_err = f"HTTP {response.status_code}"
                time.sleep(2 * (attempt + 1))
                continue
            response.raise_for_status()
            return response_content(response.json())
        except requests.RequestException as exc:
            last_err = str(exc)
            time.sleep(2 * (attempt + 1))
    raise SystemExit(f"VLM judge 调用失败（重试 {max_retries} 次后）：{last_err}")


def normalize(payload, cover_path, analysis, title, subtitle, vertical, pass_threshold, reference=None):
    weights = DIMENSION_WEIGHTS_WITH_REF if reference else DIMENSION_WEIGHTS
    scores_in = payload.get("scores", {}) if isinstance(payload, dict) else {}
    scores = {key: clamp_score(scores_in.get(key)) for key in weights}

    # 对标官方时，overall 总是按权重重算（不信 VLM 自报的 overall，避免它无视主体错误仍给高分）
    if reference or payload.get("overall_score") is None:
        overall = sum(scores[key] * weight for key, weight in weights.items())
    else:
        overall = payload.get("overall_score")
    overall = clamp_score(overall)

    detected_title = payload.get("detected_title") or (payload.get("detected", {}) or {}).get("title", "")
    detected_subtitle = payload.get("detected_subtitle") or ""
    tm = title_match(title, detected_title)
    sm = title_match(subtitle, detected_subtitle) if subtitle else None

    critical = list(payload.get("critical_issues") or [])
    issues = list(payload.get("issues") or [])

    # 主标题错字门（程序侧，不完全依赖 VLM 打分）
    if tm["unreadable"]:
        issues.append("VLM 未能读出封面主标题文字，需人工复核")
    elif tm["has_typo"]:
        # 编辑距离小（1-2 字）或 VLM 也给低分 → 很可能真错字/形近字，强制 critical；
        # 距离大可能是 VLM 读偏 → 仅 issue + 提示人工复核，避免 OCR 误差导致大量 false critical。
        if tm["normalized_distance"] <= 2 or scores["title_text_correctness"] < 6:
            critical.append(
                f"主标题文字与期望不一致（疑似错字/形近字）：期望「{title}」，封面读到「{detected_title}」"
            )
        else:
            issues.append(
                f"主标题文字与期望差异较大，需人工确认是 VLM 读偏还是真错字：期望「{title}」，读到「{detected_title}」"
            )

    # 副标题错字门（封面副标题/系列标签同样可能出错字，如「桁架内力篇」→「析架内力篇」）
    if sm is not None and not sm["unreadable"] and sm["has_typo"]:
        if sm["normalized_distance"] <= 2:
            critical.append(
                f"副标题文字与期望不一致（疑似错字/形近字）：期望「{subtitle}」，封面读到「{detected_subtitle}」"
            )
        else:
            issues.append(
                f"副标题文字与期望差异较大，需人工确认：期望「{subtitle}」，读到「{detected_subtitle}」"
            )

    if scores["title_semantic_match"] < 6:
        critical.append("标题语义未正确表达视频内容（疑似牛头不对马嘴或泛泛总结）")
    if scores["text_layout"] < 6:
        critical.append("文字排版错误（挤压 / 压主体 / 断行不可读 / 贴边切边）")

    # 对标官方的两个硬门（回应「judge 10/10 不代表接近官方」）
    if reference:
        if scores.get("subject_accuracy", 10) < 5:
            critical.append(
                f"主体不准确：未围绕官方的具体主体展开（图1 主体「{(payload.get('detected') or {}).get('subject','?')}」"
                f" vs 官方「{(payload.get('detected') or {}).get('official_subject','?')}」）——疑似泛化或混入无关品牌"
            )
        if scores.get("reference_inheritance", 10) < 5:
            critical.append("未继承官方核心视觉策略/内容语境（太模板化、丢失官方封面设计感）")

    critical = list(dict.fromkeys(critical))
    issues = list(dict.fromkeys(issues))

    passed = (overall >= pass_threshold) and (len(critical) == 0)

    return {
        "passed": passed,
        "overall_score": overall,
        "pass_threshold": pass_threshold,
        "against_reference": bool(reference),
        "scores": scores,
        "detected_title": detected_title,
        "detected_subtitle": detected_subtitle,
        "title_match": tm,
        "subtitle_match": sm,
        "critical_issues": critical,
        "issues": issues,
        "detected": payload.get("detected", {}),
        "reference_gap": payload.get("reference_gap", ""),
        "recommendation": payload.get("recommendation", ""),
        "expected": {
            "title": title,
            "subtitle": subtitle,
            "cover": str(cover_path),
            "vertical": vertical,
            "reference": str(reference) if reference else "",
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Judge a single 3:4 cover with a VLM against the vertical checklist.")
    parser.add_argument("--cover", required=True, help="3:4 cover image to judge.")
    parser.add_argument("--analysis", required=True, help="analysis.json from analyze_with_vlm.py.")
    parser.add_argument("--title", required=True, help="Expected main title.")
    parser.add_argument("--subtitle", default="", help="Expected subtitle.")
    parser.add_argument("--vertical", default="tech", help="Vertical id; loads references/<vertical>_cover_checklist.md.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--pass-threshold", type=float, default=7.0, help="overall_score 合格线（默认 7.0）。")
    parser.add_argument("--reference", help="官方优质封面图。传了则 judge 对标官方打分（subject_accuracy + reference_inheritance 维度）。")
    args = parser.parse_args()

    cover = Path(args.cover).expanduser().resolve()
    if not cover.exists():
        raise SystemExit(f"Cover not found: {cover}")
    analysis_path = Path(args.analysis).expanduser().resolve()
    analysis = json.loads(analysis_path.read_text(encoding="utf-8")) if analysis_path.exists() else {}
    reference = None
    if args.reference:
        reference = Path(args.reference).expanduser().resolve()
        if not reference.exists():
            raise SystemExit(f"Reference cover not found: {reference}")

    checklist = load_checklist(args.vertical)
    prompt = build_judge_prompt(analysis, args.title, args.subtitle, checklist, reference=reference)
    payload = call_vlm(cover, prompt, reference=reference)
    report = normalize(payload, cover, analysis, args.title, args.subtitle, args.vertical, args.pass_threshold, reference=reference)

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
