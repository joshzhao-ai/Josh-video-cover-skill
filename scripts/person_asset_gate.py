#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


PERSON_HINTS = (
    "真人",
    "本人",
    "博主",
    "出镜",
    "人像",
    "人物",
    "人脸",
    "半身",
    "口播",
    "分享者",
    "创作者",
    "up主",
    "主持人",
    "戴眼镜",
)


def joined_text(analysis):
    parts = [
        analysis.get("subject_strategy", ""),
        analysis.get("cover_archetype", ""),
        analysis.get("person_policy", ""),
        analysis.get("content_summary", ""),
        analysis.get("hook_summary", ""),
        analysis.get("mood", ""),
        " ".join(map(str, analysis.get("key_elements", []))),
    ]
    return " ".join(parts)


def score_person_need(analysis):
    score = 0
    reasons = []

    if analysis.get("subject_strategy") == "real-person-from-frame":
        score += 4
        reasons.append("VLM 建议使用视频中的真人作为封面主体。")
    if analysis.get("needs_real_person_asset"):
        score += 3
        reasons.append("分析结果标记 needs_real_person_asset=true。")
    if analysis.get("person_policy") == "real-person-only":
        score += 3
        reasons.append("人物策略是 real-person-only，不能编造陌生人。")
    if "有博主" in str(analysis.get("cover_archetype", "")):
        score += 2
        reasons.append("封面类型是有博主/真人实测型。")

    text = joined_text(analysis)
    matched = [token for token in PERSON_HINTS if token in text]
    if matched:
        score += min(3, len(matched))
        reasons.append("内容里出现真人强相关线索：" + "、".join(matched[:5]) + "。")

    return score, reasons


def build_gate(analysis):
    score, reasons = score_person_need(analysis)
    requires_decision = score >= 4
    return {
        "requires_decision": requires_decision,
        "risk": "identity-critical-person" if requires_decision else "normal",
        "score": score,
        "reasons": reasons,
        "recommended_action": "ask_user_before_prompt_generation" if requires_decision else "continue",
        "safe_default": "no-person",
        "options": [
            {
                "id": "uploaded-photo",
                "label": "上传本人照片",
                "description": "身份最稳，适合个人 IP、真人口播、账号长期头像一致的封面。",
            },
            {
                "id": "no-person",
                "label": "不使用真人",
                "description": "只做主题概念封面，避免 AI 假人像；适合先快速看风格。",
            },
        ],
        "experimental_options": [
            {
                "id": "video-frame",
                "label": "用视频帧",
                "description": "实验选项。视频帧清晰度和角度不稳定，生图模型仍可能把本人重绘成陌生人，不作为默认产品路径。",
            },
        ],
        "message_zh": (
            "检测到这个视频是真人强相关内容。继续生成前需要选择人物策略："
            "上传本人照片，或不使用真人。不要直接让模型生成陌生人像。"
            if requires_decision
            else "未检测到强真人身份风险，可以继续常规封面流程。"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="Decide whether a video-cover run needs a human identity asset decision.")
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    analysis = json.loads(Path(args.analysis).expanduser().read_text(encoding="utf-8"))
    gate = build_gate(analysis)
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")

    print(gate["message_zh"])
    if gate["requires_decision"]:
        print("推荐可选：uploaded-photo / no-person")
        print("实验选项：video-frame")


if __name__ == "__main__":
    main()
