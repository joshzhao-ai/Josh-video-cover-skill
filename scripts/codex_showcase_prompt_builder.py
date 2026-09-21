#!/usr/bin/env python3
"""Build one creative plan, then adapt it to GPT Image 2 or Dreamina.

The important unit is a selected cover route, not a generic title prompt. A
4:3 request is therefore a continuation of a selected 3:4 cover, never an
unrelated re-render of the same topic.
"""

import argparse
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STYLE_PROFILES = ROOT / "references" / "style_profiles.json"
CAPABILITY_SCRIPT = ROOT / "scripts" / "detect_dreamina_capabilities.py"


def read_json(path):
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def write_json(path, payload):
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def as_list(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def joined(items, fallback=""):
    values = as_list(items)
    return "、".join(values) if values else fallback


def infer_theme(analysis):
    text = " ".join([
        str(analysis.get("name", "")),
        str(analysis.get("content_summary", "")),
        str(analysis.get("hook_summary", "")),
        joined(analysis.get("topic")),
        joined(analysis.get("key_elements")),
    ]).lower()
    if any(token in text for token in ["3d", "打印", "手办", "建模", "拆件", "模型"]):
        return "ai_3d_printing"
    if any(token in text for token in ["硬币", "抛硬币", "概率", "随机", "50%", "正反面"]):
        return "ai_probability_experiment"
    if any(token in text for token in ["codex", "claude", "agent", "skill", "工作流", "提示词"]):
        return "ai_dev_tool"
    if any(token in text for token in ["相机", "摄影", "出片", "镜头"]):
        return "camera_lifestyle"
    if any(token in text for token in ["日料", "美食", "餐", "料理"]):
        return "food_documentary"
    return "general_knowledge"


def choose_primary_copy(title, hook):
    hook_is_lead = bool(re.search(r"[?？]|\d|%|吗$|为何|凭啥|为什么|真是", hook))
    if hook_is_lead:
        return {"primary": hook, "topic_label": title, "reason": "question_or_verified_result"}
    return {"primary": title, "topic_label": hook, "reason": "topic_or_task"}


def load_profiles():
    if not STYLE_PROFILES.exists():
        return {}
    data = read_json(STYLE_PROFILES)
    return {key: value for key, value in data.items() if not key.startswith("_")}


def select_profile(analysis, person_available, explicit):
    profiles = load_profiles()
    if explicit == "none":
        return "", None
    requested = explicit if explicit != "auto" else str(analysis.get("selected_style_profile", "")).strip()
    if requested:
        if requested not in profiles:
            raise SystemExit(f"Unknown style profile: {requested}")
        return requested, profiles[requested]
    theme = infer_theme(analysis)
    if person_available and theme == "camera_lifestyle" and "camera_review_editorial" in profiles:
        return "camera_review_editorial", profiles["camera_review_editorial"]
    if person_available and theme == "ai_dev_tool" and "story_hook_black_gold" in profiles:
        return "story_hook_black_gold", profiles["story_hook_black_gold"]
    return "", None


def profile_reference(profile, ratio):
    if not profile:
        return ""
    reference = profile.get("references", {}).get(ratio, "")
    if not reference:
        return ""
    candidate = (STYLE_PROFILES.parent / reference).resolve()
    return str(candidate) if candidate.exists() else ""


def profile_directive(profile):
    if not profile:
        return ""
    return "\n".join([
        profile.get("prompt_directive", ""),
        "Avoid: " + profile.get("negative_direction", ""),
        "Thumbnail contract: " + profile.get("thumbnail_contract", ""),
    ]).strip()


def brief_from_analysis(analysis, title, hook, subtitle):
    objects = as_list(analysis.get("visual_proof_objects")) or as_list(analysis.get("key_elements"))
    chain = as_list(analysis.get("proof_chain"))
    if not chain:
        chain = [analysis.get("low_barrier_input") or title, analysis.get("technical_path") or subtitle, analysis.get("high_value_result") or hook]
    elif len(chain) > 3:
        chain = [chain[0], chain[len(chain) // 2], chain[-1]]
    non_person_objects = [
        item for item in objects
        if not any(token in item for token in ("真人", "人物", "创作者", "讲述者", "博主"))
    ]
    hero_object = str(analysis.get("hero_object", "")).strip()
    if not hero_object:
        result_hint = str(analysis.get("high_value_result", "")).strip()
        candidates = [result_hint, *non_person_objects] if result_hint else non_person_objects

        def hero_score(item):
            positives = ("成品", "结果", "实物", "实机", "打印", "手办", "作品", "前后对比", "完成", "效果")
            negatives = ("界面", "按钮", "参数", "菜单", "流程", "图标", "代码", "工作流")
            return sum(token in item for token in positives) * 3 - sum(token in item for token in negatives) * 2

        hero_object = max(candidates, key=hero_score) if candidates else (objects[0] if objects else "与主题直接相关的结果物")
    evidence_object = str(analysis.get("evidence_object", "")).strip()
    if not evidence_object:
        remaining = [item for item in non_person_objects if item != hero_object]
        evidence_object = remaining[0] if remaining else hero_object
    return {
        "theme": infer_theme(analysis),
        "content_summary": str(analysis.get("content_summary", "")),
        "cover_promise": str(analysis.get("cover_promise") or f"{title} {hook}".strip()),
        "proof_chain": [str(item) for item in chain if str(item).strip()][:3],
        "hero_object": hero_object,
        "evidence_object": evidence_object,
    }


def routes_for_theme(theme, person_available):
    person = "with_presenter" if person_available else "no_presenter"
    generic = [
        {
            "id": "hook_poster",
            "label": "钩子海报版",
            "territory": "single-message impact poster",
            "presenter": person,
            "palette": "near-black, paper white and one topic-relevant accent; no default purple-neon template",
            "layout": "one giant primary headline takes the first read; one oversized hero proof object; presenter only supports trust",
            "typography": "editorial display type with visible material and a deliberate keyword contrast",
        },
        {
            "id": "proof_editorial",
            "label": "证据编辑版",
            "territory": "editorial proof story",
            "presenter": person,
            "palette": "restrained ink, bone, warm accent and one low-contrast topic color",
            "layout": "headline first, then one large evidence object; at most one short input-to-result relationship, never a dashboard",
            "typography": "bold editorial typography with paper, brush, print or cutout texture",
        },
        {
            "id": "tangible_scene",
            "label": "实物场景版",
            "territory": "tangible result scene",
            "presenter": person if person_available else "no_presenter",
            "palette": "photographic, physical materials and theme-led color instead of a generic technology gradient",
            "layout": "real result object or scene dominates; headline locks into clean negative space; evidence is physical rather than UI-heavy",
            "typography": "high-impact poster lettering integrated with the scene, not a floating software card",
        },
    ]
    if theme == "ai_probability_experiment":
        generic[0].update({
            "id": "question_supergraphic",
            "label": "问题冲击版",
            "palette": "near-black, warm gold, off-white and a restrained electric-cyan accent",
            "layout": "make the question the giant supergraphic; topic label is smaller; a diagonal heads-versus-tails coin is the hero",
            "typography": "thick dimensional question typography with gold/white contrast and deep black separation",
        })
        generic[1].update({
            "id": "experiment_proof",
            "label": "实验验证版",
            "layout": "a large coin and one clear probability evidence object; only one compact experiment relationship, no card grid",
        })
        generic[2].update({
            "id": "science_editorial",
            "label": "科学编辑版",
            "palette": "ink black, cream paper, brass and a minimal blue data accent",
            "layout": "editorial science-cover composition with a tactile coin experiment rather than a technology dashboard",
        })
    elif theme == "ai_3d_printing":
        generic[0].update({
            "id": "result_showcase",
            "label": "成品冲击版",
            "layout": "the printed figure/result is massive and tangible; the input image and one conversion cue only prove the transformation",
            "palette": "dark navy, clean white, cyan and one material color from the actual result",
        })
        generic[1].update({
            "id": "input_to_result",
            "label": "一图变实物版",
            "layout": "one short chain: source image -> model -> finished print; three large beats maximum",
        })
        generic[2].update({
            "id": "maker_scene",
            "label": "创客实物版",
            "layout": "real maker desk, print parts and finished object; headline uses clean empty space",
        })
    elif theme == "ai_dev_tool":
        generic[0].update({
            "id": "outcome_editorial",
            "label": "结果编辑版",
            "palette": "near-black, paper white and warm gold; avoid cyan dashboards unless the video itself is about an interface",
            "layout": "one result-led headline, large foreground presenter when provided, one proof object such as a file or method note",
        })
        generic[1].update({
            "id": "method_proof",
            "label": "方法证据版",
            "layout": "one document, method card or result screen proves the content; no capability maps or long workflow lists",
        })
        generic[2].update({
            "id": "work_scene",
            "label": "使用场景版",
            "layout": "a believable work scene shows the tool producing a result; title owns the most readable area",
        })
    return generic


def profile_routes(routes, profile_id):
    if profile_id != "creator_product_interaction":
        return routes
    interactions = [
        {
            "id": "creator_hold",
            "label": "真人持物版",
            "territory": "tactile creator-and-brand hero poster",
            "layout": "one giant short headline above; presenter and one official brand object form a strong triangle through a believable two-hand hold; the object has real volume, material and light",
            "palette": "near-black, paper white and the current brand's one official accent color; never inherit Kimi blue for another brand",
            "typography": "massive compact editorial display lettering with one brand-color keyword; no generic neon outline",
        },
        {
            "id": "creator_forward",
            "label": "广角递近版",
            "territory": "wide-angle product-to-lens interaction",
            "layout": "the same official brand object is pushed toward the lens with a 24-28mm wide-angle feeling; presenter reacts just behind it; giant headline remains the first read and interlocks through depth",
            "palette": "near-black, paper white and the current brand's one official accent color; foreground glow comes only from the brand object",
            "typography": "oversized compressed headline integrated with foreground perspective; title must remain larger than the face and product label",
        },
        {
            "id": "creator_dynamic",
            "label": "动态互动版",
            "territory": "playful creator reaction and branded-object action",
            "layout": "one memorable action such as magnetic pull, opening or controlled movement connects presenter and official brand object; expression is lively but identity stays exact; no comparison opponent",
            "palette": "brand-led cinematic contrast with restrained particles or motion streaks; no dashboard, card grid or default blue-purple technology wash",
            "typography": "one large judgment headline with tactile material and energetic angle; no small explanatory modules",
        },
    ]
    adapted = []
    for route, interaction in zip(routes, interactions):
        current = dict(route)
        current.update(interaction)
        adapted.append(current)
    return adapted


def source_contract(source_cover, source_route, copy, route):
    if not source_cover:
        return ""
    return "\n".join([
        "Selected-cover continuation contract:",
        "- The input image marked selected_vertical_reference is the user-selected 3:4 cover. It is the same campaign, not loose inspiration.",
        f"- Preserve the same click lead: 「{copy['primary']}」; preserve topic label: 「{copy['topic_label']}」.",
        f"- Preserve the selected route's message, hero category, palette mood, typography material and presenter/hero relationship from route {source_route or route['id']}.",
        "- Recompose natively for 4:3. Do not crop, stretch, paste, mechanically extend, or merely spread the vertical cover sideways.",
        "- Preserve campaign invariants, not pixel coordinates. You may rebuild line breaks, camera angle, scale, depth order and interaction staging for a native horizontal thumbnail.",
        "- The primary hook must still own roughly 45-60% of the visual area. The hero and presenter may cross the center line, overlap the headline, or use foreground perspective; do not force a rigid left-text/right-person split.",
        "- If the selected interaction becomes weak in 4:3, re-stage the same person and same hero with a closer wide-angle foreground while keeping the exact copy and campaign identity.",
        "- Do not replace the selected hero with a different concept, alter the person identity, or downgrade the question/result into a tiny subtitle.",
    ])


def ratio_contract(ratio, copy):
    if ratio == "3:4":
        return "\n".join([
            "Canvas contract: native 3:4 vertical short-video cover. Never return 9:16, 2:3, a long poster, borders or sidebars.",
            f"Hierarchy contract: primary text 「{copy['primary']}」 owns the upper or upper-left 40-55% of the canvas; topic label 「{copy['topic_label']}」 is visibly secondary.",
            "Keep title, face and hero object inside generous safe margins. Make the hero and the title overlap or interact as one composition, not stacked modules.",
        ])
    return "\n".join([
        "Canvas contract: native 4:3 horizontal cover. Never return 16:9, 3:2, a cropped vertical cover, borders or a left-text/right-image collage.",
        f"Hierarchy contract: primary text 「{copy['primary']}」 is the first thumbnail read and owns roughly 45-60% of the visual area; topic label 「{copy['topic_label']}」 is secondary.",
        "Build an independent horizontal hierarchy. The hero/presenter may sit left, right or cross the center; use scale, depth, overlap and foreground perspective so headline, person and hero feel like one poster rather than separate panels.",
        "Keep the face large enough to read at 320x240. Never solve horizontal space by shrinking the headline or pushing the person into the distance.",
    ])


def copy_contract(title, hook, subtitle, primary):
    lines = [
        "Exact Chinese copy contract:",
        f"- Topic/title text: 「{title}」",
        f"- Click lead text: 「{hook}」",
        f"- Primary thumbnail text is: 「{primary}」",
    ]
    if subtitle:
        lines.append(f"- Optional small promise line: 「{subtitle}」")
    lines.extend([
        "Render every supplied Chinese character exactly once, clearly and without repeated, missing, overlapped, garbled or cropped characters.",
        "Do not invent any other Chinese text, labels, UI copy, lists, logo, watermark, QR code, signature or platform mark.",
        "Any evidence card may use only abstract marks or the supplied short copy. Never put dense small text on a card.",
    ])
    return "\n".join(lines)


def references_for(route, ratio, portrait, source_cover, style_reference):
    refs, roles = [], []
    if route["presenter"] == "with_presenter" and portrait:
        refs.append(str(Path(portrait).expanduser().resolve()))
        roles.append("identity_reference")
    if source_cover:
        refs.append(str(Path(source_cover).expanduser().resolve()))
        roles.append("selected_vertical_reference")
    if style_reference:
        refs.append(style_reference)
        roles.append("style_reference")
    return refs, roles


def reference_prompt(refs, roles):
    if not refs:
        return "No input images are supplied. Do not create a recognisable invented presenter."
    lines = ["Input image roles:"]
    for index, role in enumerate(roles, start=1):
        if role == "identity_reference":
            detail = (
                "lock the real presenter's face, hair or hat, visible wardrobe and natural anatomy; "
                "preserve clothing category, neckline, sleeve length, color, fabric and any clearly visible chest print"
            )
        elif role == "selected_vertical_reference":
            detail = "preserve campaign identity and visual hierarchy while recomposing for 4:3; do not crop, stretch or copy pixels"
        elif role == "content_reference":
            detail = (
                "preserve the current video's real subject, product or result evidence; when it is an official brand asset, "
                "preserve its exact silhouette, logo geometry, proportions and official colors; ignore unrelated source text, watermark, UI labels and layout"
            )
        else:
            detail = (
                "learn only hierarchy, typography, palette, material treatment and information density; "
                "never copy its text, people, face, hair, pose, clothing, accessories, facts, UI, logo or subject"
            )
        lines.append(f"- Image {index}: {role}; {detail}.")
    return "\n".join(lines)


def dreamina_reference_prompt(roles, preserve_official_brand=False):
    if not roles:
        return "不使用参考图，不要虚构可识别真人。"
    lines = ["参考图角色："]
    for index, role in enumerate(roles, start=1):
        if role == "identity_reference":
            detail = "只锁定本人身份、完整上半身姿态、帽子或发型、领口、袖型和服装；删除原背景、字幕、水印和椅子"
        elif role == "content_reference":
            detail = (
                "这是当前主题唯一官方品牌物；严格保留Logo几何、轮廓、比例、纹理和官方颜色，删除参考图外部空白、水印和无关元素"
                if preserve_official_brand
                else "只提取当前视频真实的结果世界或成品；删除截图中的边框、菜单、图标、按钮、字幕、水印和所有小字"
            )
        elif role == "selected_vertical_reference":
            detail = "这是用户选中的竖版系列成片；继承同一标题、人物、主视觉关系、色彩和字体材质，并按原生4:3重新组织位置与尺度"
        else:
            detail = "只学构图、字体材质和配色；严禁复制其中的人脸、衣服、文字、UI、品牌和主体"
        lines.append(f"- 图{index}：{detail}。")
    return "\n".join(lines)


def dreamina_prompt_for(analysis, brief, copy, route, ratio, profile_id, profile, source_cover, source_route, refs, roles):
    """Dreamina works best with a short visual recipe, not the Image2 brief."""
    del analysis, source_cover
    copy_items = []
    for item in (copy["title"], copy["hook"], copy.get("subtitle", "")):
        if item and item not in copy_items:
            copy_items.append(item)
    exact_copy = "、".join(f"「{item}」" for item in copy_items)
    route_id = route["id"]
    has_presenter = route.get("presenter") == "with_presenter" and "identity_reference" in roles
    has_official_brand = profile_id == "creator_product_interaction" and "content_reference" in roles

    if ratio == "3:4":
        canvas = "原生3:4竖版短视频封面，画布比例严格为3:4"
        layouts = {
            "impact": "超大标题占上方45%；真人半身在右下约40%，做指向或展示动作；一个结果物在左下，与人物和标题互相遮挡咬合",
            "proof": "超大标题占左上40%；真人半身在左下约38%；一个结果物在右下放大，只用一条简洁动线连接，不做信息卡片",
            "scene": "超大标题压在上方；主题结果场景满版进入中下部；真人半身在右下前景，共享同一光影和景深",
        }
    else:
        canvas = "原生4:3横版短视频封面，画布比例严格为4:3，按横版重新组织构图"
        mode = route.get("variant_mode", "faithful")
        layouts = {
            "impact": "超大标题占左侧55%-60%；真人半身在右侧约38%，做指向或展示动作；一个结果物横跨中下部，把人物和标题连成整体",
            "proof": "超大标题占左上约52%；真人半身在左下约32%；一个结果物在右侧放大，只保留一条短动线",
            "scene": "超大标题占左侧约55%；主题结果场景满版延伸；真人半身在右侧前景，与场景共享光线和景深",
        }
        if mode == "thumbnail":
            layouts["impact"] = "缩略图优先：超大标题占左侧约62%；真人半身在右侧约34%；一个结果物横跨下方，标题字面必须比人物更强"

    creator_layouts = {
        "3:4": {
            "creator_hold": "唯一短标题占上方40%-46%；真人中下部近景，双手自然抱持一个准确的实体品牌物；脸、双手和品牌物形成稳定三角并互相遮挡穿插",
            "creator_forward": "唯一短标题占上方38%-45%；品牌物以24-28mm广角向镜头递近，占画面30%-45%；真人在后方仍保留清晰大脸和完整双臂，近大远小但不畸变",
            "creator_dynamic": "唯一短标题占上方42%-50%，两行以内、标题基线接近水平，字面与人物发梢和品牌物边缘前后穿插；真人中下部近景约45%，与放大的准确品牌物发生向镜头递近的明确动作；表情有趣但身份稳定，三者形成连续的Z形动线",
        },
        "4:3": {
            "creator_hold": "唯一短标题占左上和上方50%-58%；真人与一个准确品牌物在右侧及中部形成抱持动作，人物和品牌物跨过中线与标题咬合，不做左右分栏",
            "creator_forward": "缩略图优先：唯一短标题占左侧55%-62%；品牌物以24-28mm广角从中下部递近镜头，真人在右后方保持大脸和完整双臂，前景可压住少量字边形成深度",
            "creator_dynamic": "标题集中占左侧和左上58%-64%，形成紧凑的两级字块；准确品牌物竖直固定在中下部独立实体底座上，真人在右侧近景只用一根清楚的食指指向品牌物，另一只手自然收回；人物与品牌物完全不接触，不托举、不悬浮、不做含糊的半接半捧动作",
        },
    }

    impact_routes = {"hook_poster", "question_supergraphic", "result_showcase", "outcome_editorial", "creator_hold"}
    proof_routes = {"proof_editorial", "experiment_proof", "input_to_result", "method_proof", "creator_forward"}
    family = "impact" if route_id in impact_routes else "proof" if route_id in proof_routes else "scene"
    layout = creator_layouts.get(ratio, {}).get(route_id, layouts[family])
    if ratio == "4:3" and profile_id == "creator_product_interaction" and route.get("variant_mode") == "thumbnail":
        creator_thumbnail_layouts = {
            "creator_hold": "缩略图优先：唯一短标题占左侧58%-62%；真人在右侧约38%，抱持的准确品牌物跨过中线进入标题下方；脸、手和品牌物都保持大而清楚，不做左右分栏",
            "creator_forward": "缩略图优先：唯一短标题占左侧58%-62%；准确品牌物从中下部以24-28mm广角递近成为最大前景，真人在右后方保持大脸和完整双臂；前景可压住少量字边但不挡关键字",
            "creator_dynamic": "缩略图优先：标题占左侧及左上60%-66%，两行以内并形成一个完整重字块；准确品牌物竖直固定在中下部独立实体底座上，真人在右侧保持大脸，只用一根清楚的食指指向品牌物，另一只手自然收回；人物与品牌物完全不接触，不托举、不悬浮、不做含糊的半接半捧动作；标题、品牌物和脸形成强三角，320x240下仍先读标题",
        }
        layout = creator_thumbnail_layouts.get(route_id, layout)
    if not has_presenter:
        layout = re.sub(r"；真人半身[^；，]*[；，]", "；", layout)

    if profile_id == "creator_product_interaction":
        creator_styles = {
            "creator_hold": "高级创作者产品海报，近黑工作室、纸白或银灰大字、只使用当前品牌官方强调色；品牌物有真实厚度、材质、反射和统一轮廓光",
            "creator_forward": "高级广角商业海报，近黑空间、纸白或银灰大字、只使用当前品牌官方强调色；前景品牌物与真人共享同一主光、景深和速度感",
            "creator_dynamic": "高端AI新品发布杂志海报，近黑与深海军蓝创作者工作室；超大标题是具有厚度、金属倒角和投影的银白编辑字，Kimi K3 或关键词用官方蓝侧光强调；品牌物做近景实体并与人物共享同一轮廓光，背景使用低对比设备光带、速度线和少量粒子，画面饱满、有舞台感和强烈点击冲击",
        }
        visual_style = creator_styles.get(route_id, creator_styles["creator_dynamic"])
    elif profile and "黑金" in str(profile.get("name", "")):
        styles = {
            "impact": "成熟纪录片海报，近黑底、暖金粗粝笔刷大字、纸白、少量朱红，撕纸破口、油墨颗粒、电影级火光",
            "proof": "复古报刊编辑海报，炭黑、旧纸米白、暖金和朱红，丝网印刷、套色错位、粗颗粒、强版式",
            "scene": "高级游戏杂志封面，墨黑与古铜金，电影级明暗、景深、烟尘和刀光，标题用厚重编辑字体而非科技描边字",
        }
        visual_style = styles[family]
    else:
        styles = {
            "impact": f"高对比商业海报，主题配色取自{route['palette']}，粗壮艺术字、材质和主体穿插",
            "proof": "复古编辑海报，纸张、丝网印刷、套色和粗颗粒，避免软件界面感",
            "scene": "电影感主题场景，真实材质、前中后景和戏剧性光线，避免通用科技模板",
        }
        visual_style = styles[family]

    person = (
        "人物直接使用唯一身份参考图中的本人；完整保留可见的五官、年龄、肤色、帽子或发型、健康体型、肩宽，以及服装类别、颜色、领口、袖型和材质；写实风格化重绘，呈现完整头顶、肩膀、双臂和自然手指，仅保留人物本身"
        if has_presenter else "绝对不要真人、假人脸、手臂或主持人"
    )
    brand = (
        "品牌物严格使用官方内容参考图的轮廓、Logo几何、比例和官方颜色，呈现为一个具有真实厚度的完整实体，画面中只出现一次"
        if has_official_brand else "只使用一个与主题直接相关的结果物，不堆叠第二个主物"
    )
    subtitle = (
        f"「{copy['subtitle']}」只放在一条朱红笔刷带上；「{copy['primary']}」必须是最大的暖金或纸白粗体字"
        if copy.get("subtitle") else f"「{copy['primary']}」必须是最大的高对比粗体字"
    )
    horizontal_type = ""
    interaction_lock = ""
    if ratio == "4:3" and profile_id == "creator_product_interaction":
        horizontal_type = (
            "横版标题做成清楚有力的两级字块：若标题含英文产品名和中文结论，"
            "英文产品名只作为第一行识别锚点，高度约占画面18%-22%；中文结论独占第二行，高度约占画面36%-42%，"
            "实际字高达到英文行的1.7-2倍并成为画面第一视觉；两行左边缘对齐、字距紧、行距紧，"
            "标题基线近水平，整体旋转控制在0-2度，用金属厚度、投影、字号反差和前后遮挡制造力量；"
            "只将一个关键词着官方强调色，整个字块占画面60%-68%，与品牌物边缘形成5%-8%的视觉咬合"
        )
        if route_id == "creator_dynamic":
            interaction_lock = (
                "横版动作锁定：品牌物稳定立在独立底座或桌面上；人物使用一根清楚的食指指向它，食指尖与品牌物保留可见空隙，另一只手自然收回"
            )
    same_campaign = f"横版沿用竖版路线「{source_route}」的当前品牌配色、字体材质和同一个结果物，但重新原生构图" if ratio == "4:3" and source_route else ""
    return "。\n".join(item for item in [
        f"生成一张高点击、强设计感的{canvas}",
        f"核心主题：{brief['cover_promise']}，只画一个明确结果物：{brief['hero_object']}",
        f"构图：{layout}",
        f"视觉风格：{visual_style}；构图满版集中，具有清晰的前景、中景和背景",
        dreamina_reference_prompt(roles, preserve_official_brand=has_official_brand),
        person,
        brand,
        subtitle,
        horizontal_type,
        interaction_lock,
        same_campaign,
        f"画面可见文字仅有{exact_copy}，各出现一次且逐字准确；「{copy['primary']}」最先读到，主标题横向占画面宽度75%-90%，留安全边距",
        "除指定标题与官方品牌物外不出现其他可见文字、水印、二维码或重复主体；缩小到手机信息流仍一眼读清",
    ] if item) + "。"


def prompt_for(analysis, brief, copy, route, ratio, profile, source_cover, source_route, refs, roles):
    content = "\n".join([
        "Use case: ads-marketing",
        f"Asset: premium {ratio} Douyin / short-video cover",
        ratio_contract(ratio, copy),
        copy_contract(copy["title"], copy["hook"], copy["subtitle"], copy["primary"]),
        "Video brief:",
        f"- One-sentence content: {brief['content_summary']}",
        f"- Cover promise: {brief['cover_promise']}",
        f"- Hero proof object: {brief['hero_object']}",
        f"- One supporting evidence object: {brief['evidence_object']}",
        f"- Minimal proof story: {' -> '.join(brief['proof_chain'])}",
        "Creative route:",
        f"- Territory: {route['territory']}",
        f"- Layout: {route['layout']}",
        f"- Hero/proof treatment: make {brief['hero_object']} visually concrete; use only {brief['evidence_object']} as secondary proof.",
        f"- Palette: {route['palette']}",
        f"- Typography: {route['typography']}",
        reference_prompt(refs, roles),
    ])
    sections = [content]
    if source_cover:
        sections.append(source_contract(source_cover, source_route, copy, route))
    directive = profile_directive(profile)
    if directive:
        sections.append("Selected style family:\n" + directive)
    sections.append("\n".join([
        "Quality bar:",
        "- This must feel like a Douyin Featured thumbnail, not a course poster, PPT, dashboard or generic AI template.",
        "- One message, one large hero, one evidence object. Background UI, code, grids and particles are atmosphere only and must disappear at thumbnail size.",
        "- Do not default to blue-purple gradient, cyan outline cards or 3D outlined lettering unless this route explicitly calls for them.",
        "- If a presenter appears, show one anatomically complete real person with coherent shoulders, arms and hands; do not make the presenter small, distant or a floating cutout.",
        "- Wardrobe is an identity invariant when it is visible in the identity reference. Do not borrow a shirt, neckline, buttons, sleeves, pattern or accessory from the style reference.",
        "- Keep color contrast strong, safe margins generous and the primary hook readable at feed size.",
    ]))
    return "\n\n".join(sections)


def resolve_dreamina_model(requested):
    completed = subprocess.run(
        ["python3", str(CAPABILITY_SCRIPT), "--requested", requested],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise SystemExit(completed.stderr.strip() or completed.stdout.strip())
    return json.loads(completed.stdout)


def request_api(engine, refs, roles, model_info, ratio, prompt, dreamina_resolution="2k"):
    if engine == "image2":
        return {"api": "image_gen", "model": "gpt-image-2", "reference_images": refs, "reference_roles": roles}
    image_refs = refs
    api = "image2image" if image_refs else "text2image"
    command = [model_info.get("cli") or "dreamina", api]
    if image_refs:
        command.append("--images=" + ",".join(image_refs))
    command.extend([
        "--prompt=" + prompt,
        "--ratio=" + ratio,
        "--resolution_type=" + dreamina_resolution,
        "--model_version=" + model_info["resolved_model"],
        "--poll=0",
    ])
    return {
        "api": api,
        "model": model_info["resolved_model"],
        "reference_images": image_refs,
        "reference_roles": roles,
        "dreamina_command": command,
    }


def load_copy_and_person(args):
    job = read_json(args.job) if args.job else None
    if job:
        expected = "ready_for_vertical_generation" if args.ratio == "3:4" else "ready_for_landscape_generation"
        if job.get("phase") != expected:
            raise SystemExit(f"Job is not ready for {args.ratio}; current phase is {job.get('phase')}.")
        copy = dict(job.get("copy") or {})
        if not copy.get("title") or not copy.get("hook"):
            raise SystemExit("The job has no user-confirmed title copy.")
        person_mode = job.get("person_mode", "auto")
        portrait = job.get("portrait", "")
        pose_reference = job.get("pose_reference", "") or args.pose_reference
        source = (job.get("selected_vertical") or {}).get("image", "") if args.ratio == "4:3" else ""
        source_route = (job.get("selected_vertical") or {}).get("route", "") if args.ratio == "4:3" else ""
    else:
        copy = {"title": args.title.strip(), "hook": args.hook.strip(), "subtitle": args.subtitle.strip()}
        if not copy["title"] or not copy["hook"]:
            raise SystemExit("--title and --hook are required without --job.")
        person_mode = args.person_mode
        portrait = args.portrait
        pose_reference = args.pose_reference
        source, source_route = args.source_cover, args.source_route
    if args.title and job and args.title.strip() != copy["title"]:
        raise SystemExit("--title differs from the user-confirmed title in the job.")
    if args.hook and job and args.hook.strip() != copy["hook"]:
        raise SystemExit("--hook differs from the user-confirmed hook in the job.")
    if args.subtitle and job and args.subtitle.strip() != copy.get("subtitle", ""):
        raise SystemExit("--subtitle differs from the user-confirmed subtitle in the job.")
    if args.ratio == "4:3" and not source:
        raise SystemExit("4:3 requires --job with a selected 3:4 cover, or --source-cover and --source-route.")
    if source and not Path(source).expanduser().exists():
        raise SystemExit(f"Selected 3:4 cover not found: {source}")
    if portrait and not Path(portrait).expanduser().exists():
        raise SystemExit(f"Portrait reference not found: {portrait}")
    if pose_reference and not Path(pose_reference).expanduser().exists():
        raise SystemExit(f"Pose reference not found: {pose_reference}")
    return job, copy, person_mode, portrait, pose_reference, source, source_route


def build_requests(args):
    analysis = read_json(args.analysis)
    job, copy, person_mode, portrait, pose_reference, source_cover, source_route = load_copy_and_person(args)
    copy["primary"] = choose_primary_copy(copy["title"], copy["hook"])["primary"]
    copy["topic_label"] = choose_primary_copy(copy["title"], copy["hook"])["topic_label"]
    brief = brief_from_analysis(analysis, copy["title"], copy["hook"], copy["subtitle"])
    person_available = person_mode in {"uploaded-photo", "frame-cutout"} and bool(portrait)
    profile_id, profile = select_profile(analysis, person_available, args.style_profile)
    selected_style = profile_reference(profile, args.ratio)
    style_references = []
    for item in args.style_reference:
        reference = Path(item).expanduser().resolve()
        if not reference.exists():
            raise SystemExit(f"Style reference not found: {reference}")
        style_references.append(str(reference))
    if selected_style and args.engine == "image2":
        style_references.insert(0, selected_style)
    content_references = []
    for item in args.content_reference:
        reference = Path(item).expanduser().resolve()
        if not reference.exists():
            raise SystemExit(f"Content reference not found: {reference}")
        content_references.append(str(reference))
    if args.engine == "image2" and profile_id == "creator_product_interaction":
        if not content_references:
            raise SystemExit("creator_product_interaction requires an official --content-reference brand or product asset.")
        if not str(analysis.get("hero_object", "")).strip():
            raise SystemExit("creator_product_interaction requires analysis.hero_object to name the exact official brand or product object.")
    if args.engine == "dreamina" and args.dreamina_mode == "grounded" and not content_references and job:
        for item in job.get("content_references", []):
            reference = Path(item).expanduser().resolve()
            if reference.exists():
                content_references.append(str(reference))
    if args.engine == "dreamina" and args.dreamina_mode == "grounded" and args.ratio == "4:3" and not content_references and job:
        selected = job.get("selected_vertical") or {}
        manifest_value = selected.get("manifest", "")
        if manifest_value:
            manifest_path = Path(manifest_value).expanduser()
            if not manifest_path.is_absolute():
                manifest_path = Path(args.job).expanduser().resolve().parent / manifest_path
            if manifest_path.exists():
                selected_manifest = read_json(manifest_path)
                for item in selected_manifest.get("routes", []):
                    if item.get("name") == source_route or item.get("parent_route") == source_route:
                        content_references.extend(
                            ref for ref, role in zip(item.get("reference_images", []), item.get("reference_roles", []))
                            if role == "content_reference" and Path(ref).exists()
                        )
                        break
    all_routes = routes_for_theme(brief["theme"], person_available)
    all_routes = profile_routes(all_routes, profile_id)
    wanted = set(args.routes)
    if wanted:
        all_routes = [route for route in all_routes if route["id"] in wanted]
        missing = wanted - {route["id"] for route in all_routes}
        if missing:
            raise SystemExit("Unknown routes for this cover: " + ", ".join(sorted(missing)))
    if args.ratio == "4:3" and source_route:
        matching = [route for route in all_routes if route["id"] == source_route]
        if matching:
            all_routes = matching
        elif not wanted:
            all_routes = [all_routes[0]]
    model_info = resolve_dreamina_model(args.dreamina_model) if args.engine == "dreamina" else None
    out = Path(args.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    requests = []
    for route in all_routes:
        variants = [(route["id"], route)]
        if args.ratio == "4:3":
            faithful = dict(route)
            faithful["layout"] += "; native horizontal continuation: preserve campaign invariants and hero relationship, but rebuild line breaks, scale, depth and staging for 4:3"
            faithful["variant_mode"] = "faithful"
            thumbnail = dict(route)
            thumbnail["layout"] += "; thumbnail-first native 4:3: primary hook owns 45-60% of visual area; re-stage the same hero/person interaction with stronger foreground depth without changing campaign invariants"
            thumbnail["variant_mode"] = "thumbnail"
            variants = [(route["id"] + "__faithful", faithful), (route["id"] + "__thumbnail", thumbnail)]
        for route_id, variant in variants:
            identity_reference = portrait
            selected_reference = source_cover if args.engine != "dreamina" or args.dreamina_use_selected_cover else ""
            refs, roles = references_for(variant, args.ratio, identity_reference, selected_reference, "")
            if args.engine != "dreamina" or args.dreamina_mode == "grounded":
                for reference in content_references:
                    refs.append(reference)
                    roles.append("content_reference")
                for reference in style_references:
                    refs.append(reference)
                    roles.append("style_reference")
            if args.engine == "dreamina":
                prompt = dreamina_prompt_for(analysis, brief, copy, variant, args.ratio, profile_id, profile, source_cover, source_route, refs, roles)
            else:
                prompt = prompt_for(analysis, brief, copy, variant, args.ratio, profile, source_cover, source_route, refs, roles)
            prompt_file = out / f"{route_id}.prompt.txt"
            prompt_file.write_text(prompt, encoding="utf-8")
            request = {
                "name": route_id,
                "parent_route": route["id"],
                "route_label": route["label"],
                "ratio": args.ratio,
                "engine": args.engine,
                "style_profile": profile_id or "none",
                "creative_route": variant,
                "copy": copy,
                "cover_promise": brief["cover_promise"],
                "proof_chain": brief["proof_chain"],
                "hero_object": brief["hero_object"],
                "evidence_object": brief["evidence_object"],
                "source_cover": str(Path(source_cover).expanduser().resolve()) if source_cover else "",
                "source_route": source_route,
                "prompt_file": str(prompt_file),
                "prompt": prompt,
                "expected_output": str(out / f"{route_id}.png"),
                "status": "needs_image_generation",
            }
            request.update(request_api(
                args.engine,
                refs,
                roles,
                model_info,
                args.ratio,
                prompt,
                args.dreamina_resolution,
            ))
            if args.engine == "dreamina":
                request["dreamina_mode"] = args.dreamina_mode
                request["dreamina_resolution"] = args.dreamina_resolution
            requests.append(request)
    manifest = {
        "schema_version": 2,
        "engine": args.engine,
        "ratio": args.ratio,
        "workflow_job": str(Path(args.job).expanduser().resolve()) if args.job else "",
        "analysis": str(Path(args.analysis).expanduser().resolve()),
        "creative_plan": {
            "theme": brief["theme"],
            "copy": copy,
            "style_profile": profile_id or "none",
            "selected_vertical": str(Path(source_cover).expanduser().resolve()) if source_cover else "",
            "selected_route": source_route,
        },
        "review_contract": {
            "thumbnail_sizes": {"3:4": "180x240", "4:3": "320x240"},
            "must_check": [
                "primary hook is readable at feed size",
                "one-message hierarchy survives after small UI details disappear",
                "exact Chinese copy has no errors or duplication",
                "person identity and anatomy are coherent when used",
                "4:3 preserves the selected 3:4 campaign rather than merely its title",
            ],
        },
        "routes": requests,
    }
    if model_info:
        manifest["dreamina_capabilities"] = model_info
    manifest_path = out / "cover_requests.json"
    write_json(manifest_path, manifest)
    print(manifest_path)


def main():
    parser = argparse.ArgumentParser(description="Build shared creative plans and model-adapted cover requests.")
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--job", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--hook", default="")
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--person-mode", default="auto", choices=["auto", "uploaded-photo", "frame-cutout", "no-person"])
    parser.add_argument("--portrait", default="")
    parser.add_argument("--pose-reference", default="", help="Full original frame/photo used by Dreamina for pose and wardrobe grounding.")
    parser.add_argument("--ratio", required=True, choices=["3:4", "4:3"])
    parser.add_argument("--engine", default="image2", choices=["image2", "dreamina"])
    parser.add_argument("--dreamina-model", default="auto")
    parser.add_argument("--dreamina-mode", default="recipe-direct", choices=["recipe-direct", "grounded"])
    parser.add_argument(
        "--dreamina-use-selected-cover",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Pass the user-selected 3:4 cover to Dreamina as a continuation reference for native 4:3 generation "
            "(default: enabled; use --no-dreamina-use-selected-cover for native-remake fallback)."
        ),
    )
    parser.add_argument("--dreamina-resolution", default="2k", choices=["2k", "4k"])
    parser.add_argument("--style-profile", default="auto")
    parser.add_argument("--style-reference", action="append", default=[])
    parser.add_argument("--content-reference", action="append", default=[])
    parser.add_argument("--source-cover", default="")
    parser.add_argument("--source-route", default="")
    parser.add_argument("--routes", action="append", default=[])
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    build_requests(args)


if __name__ == "__main__":
    main()
