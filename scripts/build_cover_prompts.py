#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


VARIANTS = {
    "info-heavy": {
        "intent": "high information density, decisive headline space, premium tech thumbnail",
        "composition": "large clean headline area near the top, product or UI motif behind it, sharp contrast",
        "intent_zh": "信息密度高、标题区域明确、适合知识科普和工具测评的高级科技封面",
        "composition_zh": "顶部放置强标题区，中部用单一主视觉形成视觉锚点，背景信息丰富但不可读，强对比",
        "prompt_zh": "标题优先，上方大字，中部单一主视觉，背景层次丰富但不可读。",
    },
    "visual-heavy": {
        "intent": "strong visual impact, product-first composition, cinematic but concrete",
        "composition": "hero subject dominates the frame, with a clean dark headline area near the bottom",
        "intent_zh": "视觉冲击强、产品主体优先、像一张高级 AI 工具发布海报",
        "composition_zh": "主视觉占据画面主要区域，底部放置标题信息，主体清楚、冲击强、层次深",
        "prompt_zh": "主视觉优先，主体占据画面核心，底部干净暗区承接标题。",
    },
    "balanced": {
        "intent": "balanced subject and title, reliable social cover, clear mobile readability",
        "composition": "subject centered with layered depth, title-safe space across middle or lower third",
        "intent_zh": "标题和主体平衡、稳妥清晰、移动端缩略图也容易理解",
        "composition_zh": "主体和标题各占清晰层级，主视觉居中，周围有代码、界面、节点网络等上下文，标题位于中下部且清晰可读",
        "prompt_zh": "标题和主体平衡，中上部标题清楚，中部主视觉稳定。",
    },
}


PERSON_TOKENS = (
    "博主",
    "本人",
    "出镜",
    "人像",
    "人物",
    "半身像",
    "人脸",
    "表情",
    "手势",
    "up主",
    "创作者",
)


PERSON_STRONG_STRATEGIES = {"real-person-from-frame"}
PERSON_STRONG_POLICIES = {"real-person-only"}
PERSON_MODES = {"auto", "uploaded-photo", "video-frame", "no-person"}


def detect_language(title, requested):
    if requested != "auto":
        return requested
    return "zh" if any("\u4e00" <= char <= "\u9fff" for char in title) else "en"


def subtitle_from_analysis(analysis, language):
    if language == "zh":
        summary = analysis.get("content_summary", "")
        hook = analysis.get("hook_summary", "")
        joined = summary + hook
        if is_sleep_health_source(joined):
            if "1" in joined or "一小时" in joined or "只睡" in joined:
                return "每天1小时会怎样"
            return "身体正在报警"
        if is_academic_engineering_source(joined):
            # 学科教育垂类的副标题约定是「X篇」系列分类。优先用 analysis 里的 key_elements。
            for el in (analysis.get("key_elements") or []):
                s = str(el)
                if "篇" in s and len(s) <= 8:
                    return s
            return "知识篇"
        if "封" in joined:
            return "真实体验复盘"
        if "两周" in summary or "连续" in summary:
            return "两周真实感受"
        if "安装" in summary:
            return "AI助手新范式"
        if "风险" in summary:
            return "底层逻辑讲透"
        return "为什么突然出圈"
    return "Why It Matters"


def compact_text(text, limit=86):
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip("，。；、 ") + "。"


def sanitize_no_person_text(text):
    result = str(text)
    for token in PERSON_TOKENS:
        result = result.replace(token, "")
    return compact_text(result)


def filtered_elements(elements, no_person):
    if not no_person:
        return elements
    return [
        element for element in elements
        if not any(token.lower() in str(element).lower() for token in PERSON_TOKENS)
    ]


def source_text(title, analysis):
    parts = [
        title,
        analysis.get("content_summary", ""),
        analysis.get("mood", ""),
        " ".join(analysis.get("key_elements", [])),
    ]
    return " ".join(parts).lower()


def is_sleep_health_source(source):
    tokens = (
        "睡眠",
        "睡少",
        "只睡",
        "熬夜",
        "失眠",
        "心血管",
        "高血压",
        "冠心病",
        "健康",
        "sleep",
        "insomnia",
    )
    return any(token in source for token in tokens)


def is_gold_finance_source(source):
    tokens = (
        "黄金",
        "金条",
        "金价",
        "硬通货",
        "信用锚",
        "央行",
        "储备",
        "投资理财",
        "财富",
        "货币",
        "gold",
        "central bank",
    )
    return any(token in source for token in tokens)


def is_food_documentary_source(source):
    """
    检测「美食 / 饮食文化 / 餐饮纪录片」垂类。

    典型特征：黑底 + 粉笔喷溅质感大字 + 美食特写实拍 + 红色印章 / 系列角标 + 创作者水印。
    参考基准：@赛博食录 等美食 IP 的"电影海报式纪录片封面"范式。
    """
    strong_tokens = (
        # 菜系/料理类型
        "日料", "中餐", "法餐", "西餐", "韩餐", "粤菜", "川菜", "湘菜", "鲁菜", "苏菜", "闽菜", "徽菜", "浙菜",
        "寿司", "刺身", "握寿司", "天妇罗", "烤肉", "烧烤", "火锅", "麻辣烫", "螺蛳粉", "煎饼",
        "牛排", "意面", "披萨", "汉堡", "炸鸡", "披萨", "甜品", "甜点", "蛋糕", "面包",
        # 餐饮关键词
        "米其林", "餐厅", "厨师", "料理", "烹饪", "餐饮", "厨艺", "厨房", "食材", "调料", "食谱",
        "味道", "口味", "美食", "饭店", "私房菜", "外卖", "下饭",
        # 美食 IP 创作者
        "食录", "美食家", "饕餮", "餐探",
    )
    if any(token in source for token in strong_tokens):
        return True
    # 弱组合：文化/历史词 + 食物词
    food_field = ("饮食", "饭", "菜", "汤", "面", "饺子", "包子", "粽子", "馒头", "粥", "肉", "鱼", "虾", "蟹")
    context_tokens = ("文化", "历史", "起源", "发展", "传统", "工艺", "技艺", "崛起", "贵", "便宜")
    return any(f in source for f in food_field) and any(c in source for c in context_tokens)


def is_digital_review_source(source):
    """检测「数码产品测评 / 芯片技术解析 / 选购指南」no-person 子类。

    干净产品棚拍特写风（黑底 + 产品 3D + 硬朗大字），区别于 AI 工具的 cyberpunk。
    参考基准：@极客湾(天玑9400)、@橙红Iris(iPad选购) 等数码 IP 的产品特写封面。
    真人博主出镜的测评封面由 person gate 拦截，不走这条（属真人 IP 子类，暂不支持）。
    """
    tokens = (
        # 产品品类
        "手机", "平板", "电脑", "笔记本", "相机", "镜头", "耳机", "手表", "显卡", "芯片", "处理器",
        "屏幕", "键盘", "鼠标", "路由器", "充电", "电池", "soc", "cpu", "gpu", "ssd",
        # 品牌 / 型号
        "iphone", "ipad", "imac", "macbook", "airpods", "vision pro", "apple watch",
        "华为", "小米", "oppo", "vivo", "三星", "galaxy", "荣耀", "一加", "魅族", "realme",
        "天玑", "骁龙", "麒麟", "英伟达", "rtx", "联发科", "mediatek", "高通", "苹果",
        # 测评 / 解析动作
        "测评", "评测", "开箱", "上手", "首发", "跑分", "续航", "影像", "选购", "值不值",
        "参数", "配置", "性能", "技术解析", "深度体验", "买前必看", "对比实测",
    )
    s = source.lower()
    return any(token in s for token in tokens)


def is_buying_guide_source(source):
    """数码选购指南子类：多款对比 / 怎么选 / 避坑 / 全攻略（区别于单品解析）。"""
    tokens = ("选购", "怎么选", "推荐", "避坑", "买前必看", "全攻略", "怎么买",
              "值不值得买", "购买建议", "闭眼入", "性价比", "档位", "选择困难", "怎么挑")
    return any(t in source for t in tokens)


def is_academic_engineering_source(source):
    """
    检测「学科教育 / 高校课程 / 工程教学」垂类。

    这类视频的封面应该走教材课件视觉系统，而不是 AI 工具/产品发布会模板。
    典型特征：高校课程录制、学科科普、考研内容、工程示意图教学。

    判定逻辑：命中任一专业学科关键词，或同时命中教育平台词 + 学科领域词。
    保守起见，命中即认为是学科教育——误命中的代价（教材风）远低于错配到 cyberpunk
    AI 工具模板的代价（垂类完全错）。
    """
    # 专业学科核心词（这些词出现基本就是学科教育）
    strong_tokens = (
        "结构力学", "材料力学", "理论力学", "弹性力学", "流体力学", "土力学", "岩土力学",
        "桁架", "应力", "弯矩", "剪力", "内力", "腹杆", "弦杆", "拉杆", "压杆",
        "电路", "模拟电路", "数字电路", "电磁场", "电动力学", "电路图", "波形图", "相量图",
        "机械原理", "机械设计", "机械制造", "齿轮传动",
        "微积分", "线性代数", "概率论", "数学分析", "高等数学", "离散数学",
        "量子力学", "热力学", "统计物理", "凝聚态",
        "有机化学", "物理化学", "无机化学", "分析化学", "高分子化学",
        "分子生物学", "细胞生物学", "遗传学", "生物化学",
        "考研", "网课", "公开课",
    )
    if any(token in source for token in strong_tokens):
        return True
    # 弱关键词组合：教育平台/创作者词 + 学科领域词
    edu_tokens = ("湖南大学", "清华大学", "北京大学", "复旦大学", "上海交大", "浙江大学",
                  "同济大学", "哈工大", "西交大", "中山大学", "武汉大学", "南京大学",
                  "教授", "讲师", "教材", "课件", "课程", "讲解", "习题", "复习",
                  "mit", "stanford", "harvard", "cambridge",
                  "学院", "高校", "大学课", "本科生", "研究生", "硕士", "博士")
    field_tokens = ("力学", "工程", "数学", "物理", "化学", "生物", "电学", "材料",
                    "建筑", "土木", "桥梁", "结构", "机械", "电气", "通信", "信号",
                    "算法", "数据结构", "操作系统", "编译原理", "计算机网络",
                    "经济学", "金融学", "管理学", "心理学", "哲学")
    has_edu = any(t in source for t in edu_tokens)
    has_field = any(t in source for t in field_tokens)
    return has_edu and has_field


# AI 工具对决子类：参与对决的工具名「展示名 → 匹配别名」目录。
# 用于 is_ai_tool_versus_source 计数 + versus_tools 抽名。
_VERSUS_TOOL_FAMILIES = (
    ("Claude Code", ("claude code", "claudecode", "claude", "anthropic")),
    ("OpenAI Codex", ("openai codex", "codex")),
    ("ChatGPT", ("chatgpt", "gpt-5", "gpt-4", "gpt")),
    ("Cursor", ("cursor",)),
    ("GitHub Copilot", ("github copilot", "copilot")),
    ("Windsurf", ("windsurf",)),
    ("Gemini", ("gemini",)),
    ("Devin", ("devin",)),
    ("Aider", ("aider",)),
    ("Cline", ("cline",)),
    ("Trae", ("trae",)),
    ("MarsCode", ("marscode",)),
    ("通义灵码", ("通义灵码", "通义")),
    ("文心快码", ("文心快码", "文心", "comate")),
    ("Tabnine", ("tabnine",)),
)

# 泛 AI 工具语境词：当只锁定到一个具体工具时，配合它判定仍属"工具对比"。
_VERSUS_GENERIC_CTX = (
    "ai 编程", "ai编程", "ai 工具", "ai工具", "ai 助手", "ai助手", "ai 模型", "ai模型",
    "大模型", "编程助手", "代码助手", "coding agent", "ai coding", "代码生成",
)


def is_ai_tool_versus_source(source):
    """检测「AI 编程工具 / 大模型 对比·对决·二选一」子类。

    典型视频：Claude Code vs Codex、Cursor vs Copilot、GPT vs Gemini「到底选哪个」。
    这类封面的范式是「左右两个工具发光符号对撞 + 中间发光对决能量裂缝 + 顶部反转大标题」，
    它既不是单品发布会棚拍（digital_review），也不是 Claude 账号封禁踩坑（claude 路由）。
    现实中这类视频常同时含 "claude" 和 "评测/对比"，会被 claude 与 digital_review 两条路由
    抢着错配，拼出"账号封禁主体 + 单品构图"的四不像——所以本子类必须在那两条路由之前命中。

    判定：必须有"对比/对决"意图词，且锁定到 ≥2 个不同工具族，
    或锁定到 1 个具体工具 + 泛 AI 编程工具语境（如"Cursor 和别的 AI 编程工具比"）。
    """
    s = source.lower()
    versus_tokens = (
        "对比", "对决", "对垒", "对打", "之争", "二选一", "选哪个", "选哪一个",
        "哪个好", "哪个强", "哪个更", "谁更强", "谁更好", "怎么选", "选错",
        "pk", " vs ", "vs.", "vs ", " versus", "battle", "showdown", "替代",
    )
    if not any(t in s for t in versus_tokens):
        return False
    matched = sum(1 for _name, aliases in _VERSUS_TOOL_FAMILIES if any(a in s for a in aliases))
    if matched >= 2:
        return True
    return matched >= 1 and any(g in s for g in _VERSUS_GENERIC_CTX)


def versus_tools(title, analysis):
    """从 title + key_elements 抽出参与对决的两个工具展示名；不足两个用泛名补齐。"""
    s = source_text(title, analysis)
    found = []
    for display, aliases in _VERSUS_TOOL_FAMILIES:
        if any(a in s for a in aliases) and display not in found:
            found.append(display)
        if len(found) >= 2:
            break
    while len(found) < 2:
        found.append("AI 编程工具")
    return found[0], found[1]


def is_person_strong(analysis):
    if analysis.get("subject_strategy") in PERSON_STRONG_STRATEGIES:
        return True
    if analysis.get("person_policy") in PERSON_STRONG_POLICIES:
        return True
    if analysis.get("needs_real_person_asset"):
        return True
    text = " ".join([
        str(analysis.get("cover_archetype", "")),
        str(analysis.get("content_summary", "")),
        " ".join(map(str, analysis.get("key_elements", []))),
    ])
    return any(token in text for token in PERSON_TOKENS)


def require_person_decision(analysis, person_mode, person_reference):
    if person_mode not in PERSON_MODES:
        raise SystemExit(f"Unsupported --person-mode: {person_mode}")
    if is_person_strong(analysis) and person_mode == "auto":
        raise SystemExit(
            "Human identity decision required before prompt generation. "
            "Run scripts/person_asset_gate.py, ask the user to choose uploaded-photo, video-frame, or no-person, "
            "then rerun build_cover_prompts.py with --person-mode."
        )
    if person_mode in {"uploaded-photo", "video-frame"} and not person_reference:
        raise SystemExit(f"--person-reference is required when --person-mode={person_mode}.")
    if person_reference and not Path(person_reference).expanduser().exists():
        raise SystemExit(f"Person reference not found: {person_reference}")


def real_person_label(person_mode):
    if person_mode == "uploaded-photo":
        return "用户上传的本人照片"
    if person_mode == "video-frame":
        return "视频里的真实本人参考帧"
    return "人物参考图"


def subject_direction(name, title, analysis, language, person_mode):
    source = source_text(title, analysis)
    if language != "zh":
        return "Use the real video subject as the hero anchor, with contextual UI/code elements behind it."
    if "openclaw" in source:
        if name == "visual-heavy":
            return "主视觉是一个巨大的红色 3D 机械钳爪从代码终端和浏览器窗口中冲出，周围有 AI 调度节点网络。"
        if name == "balanced":
            return "中央是发光 AI 助手核心和红色钳爪符号，周围环绕浏览器窗口、代码块、节点网络。"
        return "中部用一个红色机械钳爪和半透明 AI 调度面板作为唯一主视觉。"
    if is_sleep_health_source(source) and person_mode == "no-person":
        if name == "visual-heavy":
            return (
                "主视觉不出现可识别真人、人脸或陌生主持人。使用暗夜卧室、匿名睡眠轮廓、发光闹钟、"
                "红色心电图波形和身体报警信号作为核心主体，表达长期睡眠不足对身体的冲击。"
                "画面要紧张但不恐怖，不要血腥器官或病理照片。"
            )
        if name == "balanced":
            return (
                "主视觉不出现可识别真人、人脸或陌生主持人。用夜晚床铺剪影、红色心电线、半透明人体健康面板、"
                "高血压/冠心病风险符号和闹钟组成稳定主视觉，既有生活感又有健康科普感。"
            )
        return (
            "主视觉不出现可识别真人、人脸或陌生主持人。使用红色心脏警示图标、心电图、睡眠时长数据、"
            "深夜闹钟和暗夜床铺剪影作为信息锚点，突出睡眠不足的健康风险。"
        )
    if is_gold_finance_source(source) and person_mode == "no-person":
        if name == "visual-heavy":
            return (
                "主视觉不出现真人、人脸或主持人。使用一组巨大、有重量感的 999 金条、熔化黄金流、"
                "央行金库门、全球货币网络和发光信用锚符号作为核心主体，表现黄金作为硬通货和信用锚的底层逻辑。"
            )
        if name == "balanced":
            return (
                "主视觉不出现真人、人脸或主持人。中央用金条堆叠、金币、央行金库、全球地图弧线和货币符号构成稳定主体，"
                "背景有不可读的资产配置卡片和储备比例图形，表达黄金从商品到信用锚的转换。"
            )
        return (
            "主视觉不出现真人、人脸或主持人。使用高质感金条、金币、央行金库、全球储备网络、信用锚图标和少量资产配置图形作为信息锚点，"
            "突出黄金为什么能成为全球硬通货。"
        )
    if is_food_documentary_source(source) and person_mode == "no-person":
        # 美食/饮食文化科普走「电影海报式纪录片封面」范式：纯黑暗调底 + 粉笔喷溅质感大字 +
        # 美食特写实拍主体（食物 + 手/容器/料理工具）+ 红色印章/系列角标。
        # 关键：前景手/食物要**自然遮挡**主标题下半部，产生杂志封面式 z-order 层叠感。
        elements_hint = "，".join([str(e) for e in (analysis.get("key_elements") or [])[:3]]) or "视频主题相关的代表性美食"
        layered_rule = (
            "**前后景层叠（critical）**：主体食物 + 手 / 料理工具必须**自然从画面下方向上侵入主标题文字区域**，"
            "**部分遮挡主标题的最后一行或下半部笔画**——例如手指、寿司、料理刷的尖端等遮住「贵」字的底部，"
            "形成「文字在后、食物在前」的清晰前后景空间关系，像杂志封面 model 挡住 logo 下半部那种经典设计。"
            "主体本身不要超出主标题字体的体量，主标题始终是视觉绝对主角。"
        )
        if name == "visual-heavy":
            return (
                "主视觉占画面下方约 45-55%：一个**真实美食特写实拍场景**作为画面焦点——例如一只摊开的手掌托着一颗握寿司、一支料理刷在涂酱、一双筷子夹起食物、一把厨刀切食材等典型美食 IP 构图。"
                "拍摄风格：电影感低调照明、强焦点光、暗色背景、浅景深虚化、食物质感真实可见（油亮、纹理、新鲜感）；"
                "画面氛围像舌尖上的中国、纪录片美食栏目封面，不是矢量插画、不是 3D 渲染、不是 emoji。"
                "主体食材按视频题材选择：日料 → 握寿司/刺身；中餐 → 面/饺子；法餐 → 牛排等。"
                + layered_rule
            )
        if name == "balanced":
            return (
                "主视觉占画面下方约 40-50%：真实美食特写实拍——"
                f"`{elements_hint}` 中的代表性食物作为主角，"
                "辅以人手 / 餐具 / 料理工具，电影感打光、暗色背景、强焦点。"
                "画面要像高端美食纪录片单帧，不要矢量插画、不要 3D 渲染、不要 AI 模板。"
                + layered_rule
            )
        return (
            "主视觉占画面下方约 40-50%：真实美食特写实拍作为唯一主体，"
            "暗调电影感、强焦点光、食物质感真实，不要矢量插画、不要 emoji、不要 AI 节点装饰。"
            + layered_rule
        )
    if is_academic_engineering_source(source) and person_mode == "no-person":
        # 学科教育走「极简主义工程科普海报」范式：扁平 2D 工业线框图（非 3D 立体渲染），
        # 红蓝箭头要节制（只在 4-8 个关键节点），两端必须有虚线锚定三角支座（工业制图标准）。
        # 这种渲染风格的核心参考是"奥达升 AWE《结构力学》系列封面"——扁平、克制、工业制图气质。
        flat_2d_rule = (
            "渲染风格：扁平 2D 工业线框图（critical：必须是平面 2D，不是 3D 立体建模、不是带轮廓光的 3D 渲染、不是有空间纵深的等距视图）。"
            "用纯白色或极浅米白色的细线条勾勒结构（线宽均匀、像 CAD/Adobe Illustrator 工业制图），杆件交叉处用小圆点标记节点。"
            "每个结构两端必须有'锚定三角支座'——倒立小三角形（实心或线框）下面带 3-5 条短斜线（虚线阴影），表示固定端，这是工业结构图的标志细节。\n"
            "几何严谨性（critical）：每个结构都必须左右轴对称，杆件长度按工程比例严格统一，节点位置精确等距，"
            "像 AutoCAD 或 Adobe Illustrator 用工程模板画出来的，不要手绘感、不要歪斜、不要节点错位。"
            "三个结构之间彼此宽度大致一致（占画面水平的 70-85%），垂直堆叠时高度有规律变化。\n"
            "底部留白：最下方那个结构距画面底边必须留出 5-10% 高度的纯背景呼吸空间，不要贴底、不要裁切支座斜线阴影。"
        )
        arrow_rule = (
            "箭头节制+统一化：每个结构上只叠加 4-8 个箭头（红=受压、蓝=受拉/向量），放在关键节点和主要杆件上即可，"
            "绝对不要每根杆件都画箭头、不要密集铺满。\n"
            "critical 箭头统一性：所有箭头必须用同一套 vector 风格（同样的箭杆粗细、同样的箭头三角形头部、同样的长度比例），"
            "像 Illustrator 一个 symbol 复用，不要有的粗有的细、有的是 emoji 箭头风、有的是手绘风。"
            "箭头长度约为相邻杆件长度的 30-50%，方向清晰锐利。"
        )
        if name == "visual-heavy":
            return (
                "主视觉占画面下方约 65%：垂直居中堆叠 2-3 个视频里真实出现的工程/学科结构模型"
                "（如桁架、电路、分子、几何、应力图等）。"
                f"{flat_2d_rule}{arrow_rule}"
                "结构本身要画得大、清楚、占满下半部宽度；不要 3D 立体渲染、不要漂浮发光卡片、不要应用场景 icon。"
            )
        if name == "balanced":
            return (
                "主视觉占画面下方约 60%：垂直居中堆叠 3 个视频里真实出现的工程/学科结构模型，"
                "彼此留出干净间距。"
                f"{flat_2d_rule}{arrow_rule}"
                "不要在每个结构下面加 caption 文字、不要加应用场景图标、不要加公式注解、不要加 emoji 标签。"
            )
        return (
            "主视觉占画面下方约 60%：垂直堆叠 2-3 个视频里真实出现的工程/学科结构模型。"
            f"{flat_2d_rule}{arrow_rule}"
            "结构是唯一主体，不出现应用 icon、caption 小字、装饰图。"
        )
    if is_ai_tool_versus_source(source) and person_mode == "no-person":
        # AI 工具对决：左右两个工具发光符号对撞 + 中间能量裂缝。
        # 左暖（橙/珊瑚/金）右冷（青蓝/teal）形成对决张力，是这类封面的灵魂。
        left, right = versus_tools(title, analysis)
        clash = (
            f"主体是两个 AI 编程工具的'二选一对决'：左侧代表「{left}」、右侧代表「{right}」。"
            f"左侧工具用暖色调（暖橙 / 珊瑚 / 金）发光的命令行终端 / AI 核心符号，"
            f"右侧工具用冷色调（青蓝 / teal）发光的圆角终端 / '>_' 命令行图标符号；"
            "两者左右对峙，中间一道发光的对决能量裂缝 / 闪电分割线，缝隙处火花迸发，制造两强相争的张力。"
            "工具符号里的 UI 和代码只做不可读光带，不要写出可读小字。"
            "critical：绝不出现任何真人、人脸、半身像；绝不画 Claude 账号封禁锁头 / 红色警告弹窗（那是 Claude 踩坑视频）；"
            "绝不画成单颗芯片 / 单台数码产品发布会棚拍（那是数码测评）；不要 K 线、不要 cyberpunk 霓虹乱光、不要四层背景。"
        )
        if name == "visual-heavy":
            return (
                "视觉冲击优先：画面中下方 50-60% 是两个巨大的、对峙的 AI 编程工具主视觉对撞。"
                + clash
                + "干净高级的开发者工具暗色风格，纯深炭黑背景，金属玻璃质感和边缘轮廓光。"
            )
        if name == "balanced":
            return (
                "构图均衡的工具对比：中部 40-65% 左右并置两个发光终端窗口 / 工具图标，中间一个发光的 'VS' 或对决分割。"
                + clash
            )
        return (
            "信息优先：中部 45-60% 放左右对决的两个发光命令行终端窗口，中间一道发光对决裂缝。"
            + clash
        )
    if "claude" in source and person_mode == "no-person":
        if name == "visual-heavy":
            return (
                "主视觉不出现任何真人、人脸或半身像。用一个巨大的深色代码终端/IDE 窗口作为主体，"
                "前景叠加红色账号锁定警告、封禁风险三角标、被阻断的登录卡片和闪烁的命令行光标。"
                "画面表达 Claude Code 使用踩坑和账号风险，不要股票走势、K线、金融图表。"
            )
        if name == "balanced":
            return (
                "主视觉不出现任何真人、人脸或半身像。中央是 Claude Code 开发者工作流符号："
                "一个带 Claude Code 气质的深色 IDE/CLI 终端窗口作为唯一核心主体，画面能看出开发者正在用命令行驱动代码任务，"
                "终端窗口内部嵌入醒目的红色系统封禁状态条和账号锁头图标，红条必须被屏幕边框裁切在窗口内部，"
                "红条必须贴合终端屏幕的透视角度，跟随同一个消失点，左右边缘与屏幕边框平行，不能是正面平贴的矩形。"
                "账号锁头必须是印在红色状态条上的白色扁平线性 UI 图标，和红条在同一个透视平面内，不能像独立 3D 图标浮起来。"
                "透视、反光和阴影都要和终端窗口连在一起，像账号突然被冻结的系统弹窗，而不是漂浮在画面前面的贴纸。"
                "终端窗口使用暖米白/橙金代码高亮、深石墨面板、紫棕环境光和少量青色节点。"
                "不要额外生成聊天截图、文档小窗、漂浮卡片或重叠 UI；所有界面文字只做不可读光块，画面不要散成多个小卡片，不要股票走势、K线、金融图表。"
            )
        return (
            "主视觉不出现任何真人、人脸或半身像。使用深色代码终端、Claude Code 抽象工具面板、"
            "账号封禁锁头、红色警告弹窗、被拦截的登录状态和少量飞书文档联动卡片作为封面主体。"
            "核心情绪是开发者工具踩坑和账号风险，不要股票走势、K线、金融图表。"
        )
    if is_digital_review_source(source) and person_mode == "no-person":
        if is_buying_guide_source(source):
            # 选购指南：多款不同型号铺陈 + 前景主推，体现"全档位怎么选"（两层结构）
            return (
                f"主体表现【选购对比】语境：背景铺陈大量不同型号的同类产品（标题「{title}」涉及的产品类，"
                "不同尺寸/颜色/年代/价位档，数量越多越体现'全档位'，至少 6-10 台并置），"
                "前景放一台主推产品做 3D 棚拍特写、稍大稍亮，形成'背景排 + 前景主推'两层结构，传达'这么多到底怎么选'。"
                "纯黑或深暗摄影棚底，产品金属玻璃质感、反光、轮廓光，可加少量冷色光线动势增强信息流冲击。"
                "critical 禁止：只放少量几台整齐相同产品（丢失'多选择'语境）、单一产品、官网素材式整齐陈列、"
                "cyberpunk 霓虹、AI 节点、K 线、四层背景、真人/假人脸。"
            )
        # 芯片 / 单品解析：锁定标题指向的那一个具体型号本体（根因修复：画"这一个"而非"一类"）
        return (
            f"主体必须是标题「{title}」指向的【那一个具体型号产品本身】的高质感 3D 棚拍特写——"
            "例如标题是天玑9400 就画一颗带 MediaTek 标识的天玑芯片本体；标题是某款手机就画那一款手机本体。"
            "critical 主体准确性（这是这类封面的命门）："
            "① 只画一个主体（单颗芯片 / 单台设备），绝不画成一排或多颗泛产品、不要产品阵列；"
            "② 必须带该产品自己的正确品牌标识，**绝对不要出现 Apple/苹果、骁龙/高通、英伟达/RTX 等无关或竞品 logo**；"
            "③ 主体要让人一眼认出就是标题这一款产品，不是泛化的'某芯片/某设备'。"
            "单主体居中偏下、占画面 45-55%，金属玻璃质感、边缘反光、轮廓光、悬浮投影，像产品发布会主视觉。"
            "纯黑摄影棚底；禁止：cyberpunk 霓虹、AI 节点、K 线、四层背景、代码终端、真人/假人脸、悬浮发光卡片陈列。"
        )
    if person_mode == "no-person":
        return (
            "主视觉不出现任何真人、人脸或半身像。使用 AI 行业趋势、机会窗口、纳斯达克/科技股走势、"
            "信息差卡片、节点网络和发光窗口作为封面主体。"
        )
    if analysis.get("subject_strategy") == "real-person-from-frame" and person_mode in {"uploaded-photo", "video-frame"}:
        label = real_person_label(person_mode)
        if name == "visual-heavy":
            return f"主视觉使用{label}中的真实人物身份，人物靠近镜头、表情自然可信，叠加 AI 行业趋势、纳斯达克走势、科技公司布局等抽象图形。"
        if name == "balanced":
            return f"主视觉使用{label}中的真实人物身份，人物位于中部偏上，周围用 AI 节点网络、科技资讯卡片和市场趋势光线形成知识分享氛围。"
        return f"主视觉使用{label}中的真实人物身份，人物作为可信分享者，背景加入 AI 行业趋势、科技股行情、机会窗口等不可读视觉符号。"
    if "claude" in source:
        if "讲解" in source or "麦克风" in source or "up主" in source:
            return (
                "主视觉采用无人物的 Claude Code 开发者工作流符号："
                "发光终端窗口轮廓、模糊代码光带、AI 节点网络、被划掉的问答气泡、效率跃迁光轨。"
                "界面和代码只作为不可读的形状与光影。"
            )
        return "主视觉是抽象 Claude Code 开发者工作流：发光终端轮廓、模糊代码光带、AI 节点网络和效率跃迁符号，所有 UI 不可读。"
    if "讲解" in source or "麦克风" in source or "创作者" in source:
        return "主视觉采用无人物的口播知识封面符号：麦克风、讲解手势剪影、主题图标、知识卡片和深色科技光效。"
    return "主视觉使用真实视频主题中的产品、界面或关键物体，周围加入代码面板、信息节点和科技光效。"


def composition_direction(name, title, analysis, language, person_mode):
    source = source_text(title, analysis)
    variant = VARIANTS[name]
    if language != "zh":
        return variant["composition"]
    if "openclaw" in source:
        if name == "info-heavy":
            return "上方 0-30% 保留标题安全区，中部用一个红色机械钳爪和半透明 AI 调度面板作为唯一主视觉，占画面 45%，强对比。"
        if name == "visual-heavy":
            return "一个巨大的红色 3D 机械钳爪从代码终端和浏览器窗口中冲出，占画面 55%，下三分之一保留深色标题安全区。"
        return "中央是发光 AI 助手核心和红色钳爪符号，周围环绕浏览器窗口、代码块、节点网络，占画面 45%，中下部保留标题安全区。"
    if is_sleep_health_source(source) and person_mode == "no-person":
        if name == "info-heavy":
            return "上方 0-32% 保留超大标题安全区，中部用红色心脏警示图标、心电图和睡眠时长数据作为单一信息主视觉，底部放暗夜床铺剪影。"
        if name == "visual-heavy":
            return "上方 0-30% 是超大标题和副标题，下方 45-55% 是暗夜睡眠场景；红色心电线从画面中部横穿，闹钟和身体报警光效形成强冲击。"
        return "标题位于上方干净暗区，中部用匿名睡眠场景、红色心电线和半透明健康风险面板形成稳定主视觉，标题、主体和风险符号三层清楚。"
    if is_gold_finance_source(source) and person_mode == "no-person":
        if name == "info-heavy":
            return "上方 0-32% 保留超大标题安全区，中部用 999 金条、信用锚图标和央行金库门作为单一信息主视觉，底部用金币和全球货币弧线补充财富科普氛围。"
        if name == "visual-heavy":
            return "上方 0-30% 是超大标题和副标题，中部一个巨大的金条堆或熔化黄金从金库中冲出，占画面 50-58%，形成强财富冲击。"
        return "标题位于上方干净深色区域，中部用金条堆叠、金币、金库门、全球货币网络和信用锚符号形成稳定主视觉，标题、黄金主体和底层逻辑符号三层清楚。"
    if is_food_documentary_source(source) and person_mode == "no-person":
        # 美食封面构图：超大主标题占主导 + 前景美食/手部分遮挡主标题下半，营造杂志封面前后景层叠。
        if name == "info-heavy":
            return (
                "电影海报式纪录片封面构图：左上红色印章 + 右上红色系列角标；"
                "**主标题占据画面绝大部分**（垂直 50-65%、水平 75-92%）多行竖向堆叠粉笔喷溅大字；"
                "下方 40-55% 是真实美食特写实拍主体，**主体从下方向上侵入文字区域、部分遮挡主标题下半笔画**（杂志封面式 z-order）；"
                "画面底部保持暗背景或仅露主体底边，不要加任何账号水印。"
            )
        if name == "visual-heavy":
            return (
                "电影海报式纪录片封面构图：左上印章 + 主标题超大粉笔字 + 右上系列角标；"
                "下方 45-55% 是占满画面宽度的美食特写实拍（食物 + 手/工具），**前景的手与食物必须从下方上探、部分覆盖主标题底部笔画**，"
                "形成文字在后、食物在前的强景深层叠。底部不放账号水印，保持画面干净。"
            )
        return (
            "电影海报式纪录片封面构图：上部超大主标题粉笔字 + 印章 + 系列角标；下方美食实拍主体；"
            "**前景手/食物部分遮挡主标题下半**，营造前后景空间关系；底部不放账号水印。"
        )
    if is_academic_engineering_source(source) and person_mode == "no-person":
        # 极简主义工程科普海报：上 40% 文字层级、下 60% 结构主体。
        # 文字层级强调留白和高对比，不挤、不密、不堆装饰。
        if name == "info-heavy":
            return (
                "极简主义工程科普海报构图，上 40% 是文字层级、下 60% 是结构主体：\n"
                "顶部文字层级居中排版，文字之间有充分留白，不与下方结构主体重叠；\n"
                "下方 60% 区域垂直居中堆叠 2-3 个工程结构模型，结构之间留干净间距。\n"
                "整体气质：高对比度、强视觉层级、极简留白，绝对不要塞满画面。"
            )
        if name == "visual-heavy":
            return (
                "极简主义工程科普海报构图，上 35% 是文字层级、下 65% 是结构主体：\n"
                "顶部文字居中、主标题尺寸非常大；\n"
                "下方 65% 是 2-3 个工程结构模型垂直堆叠，结构占满下半部分高度，主体感强但不挤。"
            )
        return (
            "极简主义工程科普海报构图，上 40% 是文字层级、下 60% 是结构主体，"
            "整体疏密有致、留白干净、视觉层级清楚——文字层级在上方独立成区，结构主体在下方独立成区，"
            "两个区域之间有清晰的呼吸感，不要把元素挤在一起。"
        )
    if is_ai_tool_versus_source(source) and person_mode == "no-person":
        if name == "info-heavy":
            return "上方 0-40% 是超大粗黑无衬线主标题压顶；中下 45-60% 是左右对决的两个发光终端窗口，中间一道发光对决裂缝，左右对称张力强；不出现人物。"
        if name == "visual-heavy":
            return "标题在上方 0-35% 干净暗区；下方 50-60% 是两个对峙工具主视觉对撞 + 中间发光能量裂缝作为最大锚点，冲击强；不出现人物。"
        return "标题在上方 0-38%；中部 40-65% 左右并置两个工具终端 + 中间 'VS' 对决分割，下方可留极简结果标签条；层级：标题>双工具对决>背景；不出现人物。"
    if is_digital_review_source(source) and person_mode == "no-person":
        if is_buying_guide_source(source):
            return (
                "选购指南封面构图：上方 0-38% 放**橙色/黄色高饱和超大粗标题**（冲击强、有压迫感、面积大不要克制）；"
                "下方约 60% 是'背景多型号产品铺陈 + 前景一台主推特写'两层结构，传达'全档位怎么选'；"
                "可加少量冷色光线动势增强信息流冲击感。"
            )
        if name == "info-heavy":
            return "芯片/单品解析构图：上方 0-40% 超大硬朗标题（产品名金白大字）压顶，中下 45-55% 放**单个具体产品**的 3D 棚拍特写居中偏下，底部留暗背景呼吸，层级 title>单产品>背景；不放产品阵列。"
        if name == "visual-heavy":
            return "芯片/单品解析构图：标题在上方 0-35% 暗区，下方 50-58% 是**单个具体产品**的大特写作为最大锚点，产品冲击力强，像发布会主视觉；不放多产品。"
        return "芯片/单品解析构图：标题上方金白大字，中下部 45-55% 放**单个具体产品** 3D 特写，三层清楚，画面干净不堆砌，绝不放产品阵列。"
    if "claude" in source and person_mode == "no-person":
        if name == "info-heavy":
            return "上方 0-34% 保留超大标题安全区，中部用代码终端窗口、账号锁头和红色封禁警告面板形成单一主视觉，不出现人物。"
        if name == "visual-heavy":
            return "巨大的封禁警告弹窗和深色终端窗口作为最大视觉锚点，占画面 50-58%，底部或上方留干净暗区承接标题，不出现人物。"
        return "标题位于上方 0-30% 的干净暗区，中部只放一个巨大的透视 Claude Code 风格 IDE/CLI 终端窗口，终端窗口占画面 45-55%；账号锁定图标和红色封禁状态条必须嵌在终端窗口内部，并严格跟随终端屏幕透视角度，形成单一稳定视觉锚点，不出现人物；不要漂浮小窗或辅助卡片，避免画面碎。"
    if person_mode == "no-person":
        if name == "info-heavy":
            return "上方 0-34% 保留超大标题安全区，中部用发光机会窗口、AI 节点网络和科技股走势形成单一主视觉，不出现人物。"
        if name == "visual-heavy":
            return "巨大 AI 机会窗口或上升趋势线作为最大视觉锚点，占画面 50-58%，标题放在干净暗色区域，不出现人物。"
        return "标题位于中上部，中部用 AI 节点网络、趋势线和信息差卡片形成稳定视觉锚点，不出现人物。"
    if analysis.get("subject_strategy") == "real-person-from-frame" and person_mode in {"uploaded-photo", "video-frame"}:
        if name == "info-heavy":
            return "上方 0-32% 保留超大标题安全区，中部放真人参考图中的本人半身像，人物占画面 40-50%，背景信息丰富但不可读。"
        if name == "visual-heavy":
            return "真人参考图中的本人作为最大视觉锚点，占画面 50-58%，标题放在下三分之一的干净暗色区域，人物与标题互不遮挡。"
        return "标题位于中上部，真人参考图中的本人位于中部偏下，人物占画面 42-50%，周围有 AI 趋势和机会窗口的科技氛围。"
    return variant["composition_zh"] + "。"


def intent_direction(name, title, analysis, language):
    source = source_text(title, analysis)
    variant = VARIANTS[name]
    if language != "zh":
        return variant["intent"]
    if is_sleep_health_source(source):
        if name == "info-heavy":
            return "信息密度高、标题区域明确、适合睡眠健康科普的高点击封面"
        if name == "visual-heavy":
            return "视觉冲击强、睡眠风险主体优先、暗夜健康警示封面"
        return "标题和睡眠健康主体平衡、稳妥清晰、移动端缩略图容易理解"
    if is_gold_finance_source(source):
        if name == "info-heavy":
            return "信息密度高、标题区域明确、适合黄金财经知识的高点击封面"
        if name == "visual-heavy":
            return "视觉冲击强、黄金资产主体优先、硬核财富科普封面"
        return "标题和黄金主体平衡、财经知识感清晰、移动端缩略图容易理解"
    if is_food_documentary_source(source):
        if name == "info-heavy":
            return "电影海报式美食纪录片封面、暗调高对比、粉笔喷溅大字 + 真实美食特写、@创作者品牌印章感"
        if name == "visual-heavy":
            return "美食特写实拍主体强冲击、纪录片单帧质感、暗调电影感、强焦点光"
        return "标题和美食主体平衡、暗调电影海报感、移动端缩略图食欲诱发"
    if is_academic_engineering_source(source):
        if name == "info-heavy":
            return "标题信息层级丰富、副标题作系列分类、像教材课件或高校公开课视频片头"
        if name == "visual-heavy":
            return "学科示意图作为主体强冲击、像教材封面、教学公信力强"
        return "标题和学科示意图平衡、教材课件感、移动端缩略图也能看清是哪个学科"
    if is_ai_tool_versus_source(source):
        if name == "info-heavy":
            return "标题与'二选一'决策优先、像 AI 工具对比测评封面，干净高级有对决张力"
        if name == "visual-heavy":
            return "两个工具对撞主视觉强冲击、像巅峰对决海报、暗色高级开发者工具质感"
        return "标题与双工具对决平衡、清晰理性的二选一决策感、移动端缩略图一眼看懂在比什么"
    if is_digital_review_source(source):
        if name == "info-heavy":
            return "标题信息明确、产品卖点/型号突出、像数码评测栏目封面，干净高级"
        if name == "visual-heavy":
            return "产品 3D 特写强冲击、像产品发布会主视觉、冷峻高级质感"
        return "标题和产品主体平衡、干净高级科技感、移动端缩略图能一眼认出是什么产品"
    return variant["intent_zh"]


def palette_direction(title, analysis, language):
    source = source_text(title, analysis)
    if language != "zh":
        return "Use a restrained premium palette with one vibrant accent, a dark base, and white/gold text."
    if "openclaw" in source:
        return "深蓝黑渐变底，主色为高饱和红色，辅色为青色光和少量金色。"
    if is_sleep_health_source(source):
        return "深蓝黑、石墨黑和低饱和紫蓝作为夜晚底色，红橙色只用于心电线、身体报警和健康风险焦点，标题用米白金色高对比字效。整体像高级健康科普封面，不要医院恐怖片质感。"
    if is_gold_finance_source(source):
        return "深黑、炭黑和低饱和皇家蓝作为高级财富底色，主色为真实金属金、琥珀金和暖白高光，辅以少量红色风险提示和冷蓝货币光线。整体像高级财经知识封面，不要廉价暴富海报。"
    if is_food_documentary_source(source):
        return (
            "**纯黑色或深炭黑暗调背景**（#0A0A0A 到 #1A1614 区间），不要深蓝、不要梯度光斑、不要网格纹理；"
            "主标题用**白色或近白米色粉笔喷溅风格大字**——字面有明显的粉笔颗粒感、墨迹喷溅、撕裂残破边缘、磨损 noise 纹理，"
            "**绝对不要 3D 立体厚切、不要金属拼装、不要螺丝铆钉**（那是工程教学的字体气质，会让画面错位）；"
            "印章/系列角标用**高饱和暖红色 #C92A2A 到 #E03434 区间**作为唯一点缀色（小面积、仅用于品牌印章和系列标签）；"
            "美食主体保留**食材真实自然色 + 暗调电影感打光**（暖橙色高光、深褐色阴影、低饱和中间调），"
            "整体像舌尖上的中国、料理人 等高端纪录片单帧——电影感、克制、留白。"
            "禁止：cyberpunk 霓虹、青色科技光、AI 节点发光、矢量插画感、emoji 化食物。"
        )
    if is_academic_engineering_source(source):
        return (
            "深邃的深蓝色纯净背景（学院深蓝 #0E1A33 到 #1A2A4D 区间），不要任何网格暗纹、不要电路纹理、不要梯度光斑；"
            "主标题用纯白色立体拼接风格大字，三维厚度，几何切割感，正面漫反射光、顶部冷调轮廓光勾边，整体悬浮感清晰但克制；"
            "标签色块用高饱和度橙色矩形（橙底黑字）和纯白色矩形（白底黑字）做对比，色块边缘锐利；"
            "工程结构模型用纯白色或浅米白色精确线条绘制（工业图纸感），杆件/节点上叠加高饱和度的红色（受压/拉/关键节点）"
            "和蓝色（向量/流/辅助）指示箭头，色彩与深蓝背景形成强烈的冷暖反差。"
            "整体像极简主义工程科普海报，绝不要 cyberpunk 霓虹、不要发光全息卡片、不要 AI 产品发布会的青色科技光。"
        )
    if is_ai_tool_versus_source(source):
        return (
            "纯深炭黑 / 石墨黑摄影棚暗底（不要 cyberpunk 霓虹乱光、不要四层背景、不要 K 线、不要网格电路）；"
            "左工具暖色系（暖橙 / 珊瑚 / 金）、右工具冷色系（青蓝 / teal），中间对决裂缝用高对比白热火花光；"
            "金属玻璃质感、边缘轮廓光；主标题用白色 / 金白渐变粗黑超粗无衬线大字，强描边阴影，缩略图极醒目。"
        )
    if is_digital_review_source(source):
        title_color = (
            "主标题用**橙色或黄色高饱和超大粗黑无衬线字**（选购指南要强冲击、抓眼）"
            if is_buying_guide_source(source)
            else "主标题用白色/金白渐变/银色粗黑硬朗无衬线大字（产品名金属质感）"
        )
        return (
            "纯黑或深炭黑摄影棚暗底（不要深蓝、不要网格电路、不要梯度光斑、不要四层背景）；"
            "产品有真实金属/玻璃质感、边缘反光、轮廓光、轻微悬浮投影；"
            f"主色冷调高级感（银/香槟金/紫/白），主色≤3，高对比；{title_color}，识别度高。"
            "整体像产品发布会主视觉或数码评测栏目封面，干净、冷峻、高级，绝不要 cyberpunk 霓虹、不要 AI 节点发光、不要 K 线。"
        )
    if "claude" in source:
        return "深石墨黑到紫棕黑渐变底，主色为 Claude 气质的暖橙、米白和低饱和紫棕，辅色为少量青色代码光；红色只用于封禁警告和风险焦点。避免普通蓝紫霓虹 AI 风，整体更像高级开发者工具、CLI 终端和代码编辑器的质感，有大片暗部留白、强轮廓光和高级玻璃/金属质感。"
    return "深蓝黑或炭黑渐变底，使用一个高饱和主色、青色科技光和少量金色强调。"


def forbidden_direction(title, analysis, language, person_mode):
    source = source_text(title, analysis)
    if language != "zh":
        return "No watermark, no QR code, no fake platform badge, no unreadable extra text."
    if "openclaw" in source:
        return "不要生成二维码、水印、平台角标、假 logo、人物半身像、箭头贴纸、emoji；背景 UI 不要有可读小字。"
    if is_sleep_health_source(source) and person_mode == "no-person":
        return "不要生成二维码、水印、平台角标、假 logo、可识别真人、人脸、陌生主持人、血腥器官、病理照片、恐怖画面、办公数码界面、编程开发元素、金融行情元素、emoji、箭头贴纸；除主标题和副标题外不要出现任何可读小字。"
    if is_gold_finance_source(source) and person_mode == "no-person":
        return "不要生成二维码、水印、平台角标、假 logo、可识别真人、人脸、陌生主持人、无关数码界面、无关软件界面、廉价暴富元素、emoji、箭头贴纸；除主标题和副标题外不要出现任何可读小字。"
    if is_food_documentary_source(source) and person_mode == "no-person":
        return (
            "不要生成二维码、平台角标、假 logo、明星脸、卡通人物、虚假主播；"
            "**明确禁止以下错误垂类元素**：代码终端 / IDE / 浏览器 UI、AI 节点关系网络、神经网络图、K 线 / 股票走势 / 纳斯达克、"
            "财务图表、加密货币、cyberpunk 霓虹发光、青色科技体积光、漂浮粒子辉光、发光全息卡片、科幻 HUD、"
            "桁架 / 工业制图 / CAD 线框、扁平 vector 几何示意图、3D 金属立体字 + 螺丝铆钉钉头（属于工程教学）、"
            "图表 / 柱状图 / 数据可视化（这是数据科普范式，不是美食）。"
            "美食主体本身不要画成 emoji 化、卡通化、矢量插画化——必须是真实摄影特写质感。"
            "画面里除主标题、左上印章文字、右上角标文字、底部账号水印外，不要出现任何其他可读小字（不要菜单文字、不要日期、不要 caption）。"
        )
    if is_academic_engineering_source(source) and person_mode == "no-person":
        return (
            "不要生成二维码、水印、平台角标、假 logo、真人、人脸、半身像、陌生人物、明星脸、卡通人；"
            "明确禁止：代码终端/IDE 窗口、命令行光标、浏览器/网页 UI、AI 节点关系网络、神经网络节点图、"
            "K 线/股票走势/纳斯达克曲线/财务报表、加密货币元素、cyberpunk 霓虹发光、青色科技体积光、漂浮粒子辉光、发光全息卡片、科幻 HUD；"
            "更明确禁止以下'教学装饰元素'（这些会让画面变密、丢失极简感）：每个结构下面的 caption 文字小字、"
            "🏠/🏛/🌉 等应用场景 emoji 或 icon、公式注解小字（如'N=弦杆内力'）、bullet 点状标签、"
            "底部 bilibili/校徽水印、教材章节小字、目录号、序号、坐标轴标注；"
            "除主标题、kicker 小字、彩色矩形标签上的文字外，画面里不要出现任何其他可读文字。"
        )
    if is_ai_tool_versus_source(source) and person_mode == "no-person":
        return (
            "不要任何真人、人脸、半身像、明星脸、卡通人；"
            "明确禁止错误垂类元素：Claude 账号封禁锁头 / 红色警告弹窗（那是 Claude 踩坑视频）、"
            "单颗芯片 / 单台数码产品发布会棚拍（那是数码测评）、K 线 / 股票走势 / 财务图表、"
            "cyberpunk 霓虹乱光、四层背景、网格电路纹理、AI 节点关系网、假 logo、二维码、平台角标；"
            "两个工具符号里的 UI 和代码只做不可读光块；除主标题和副标题外不要出现任何可读小字。"
        )
    if is_digital_review_source(source) and person_mode == "no-person":
        return (
            "不要生成二维码、平台角标、假 logo、任何真人、人脸、半身像、明星脸、卡通人；"
            "明确禁止错误垂类元素：cyberpunk 霓虹发光、青色科技体积光、AI 节点关系网络、神经网络图、"
            "K 线/股票走势/财务图表、代码终端/IDE/浏览器 UI、四层背景、漂浮粒子辉光、科幻 HUD、"
            "学科教材风（深蓝立体字+螺丝铆钉、工业线框）、emoji 化/卡通化/矢量化产品；"
            "产品必须是真实棚拍质感；除主标题和副标题外不要出现任何可读小字。"
        )
    if "claude" in source and person_mode == "no-person":
        return "不要生成二维码、水印、平台角标、假 logo、官方品牌 logo、任何真人、人脸、半身像、陌生人物、明星脸、卡通人、股票K线、金融走势图、收益曲线、箭头贴纸、emoji、聊天截图、文档小窗、漂浮卡片、重叠 UI；背景 UI、代码和卡片不要有可读小字，除主标题和副标题外不要出现任何文字。"
    if person_mode == "no-person":
        return "不要生成二维码、水印、平台角标、假 logo、任何真人、人脸、半身像、陌生人物、明星脸、卡通人、箭头贴纸、emoji；背景 UI、行情和资讯卡片不要有可读小字。"
    if analysis.get("subject_strategy") == "real-person-from-frame" and person_mode in {"uploaded-photo", "video-frame"}:
        return "不要生成二维码、水印、平台角标、假 logo、陌生人物、明星脸、卡通人、箭头贴纸、emoji；人物必须来自参考图的本人身份，不要改成另一个人；背景 UI、行情和资讯卡片不要有可读小字。"
    return "不要生成二维码、水印、平台角标、假 logo、人物半身像、箭头贴纸、emoji、布局标注、百分号、比例数字；背景 UI 不要有可读小字。"


def visual_system_direction(title, analysis, language, person_mode):
    source = source_text(title, analysis)
    if language == "zh" and is_sleep_health_source(source):
        return (
            "采用高冲击健康科普封面：全出血画面，不要白边和内框；"
            "画面必须只属于睡眠健康题材，不使用办公数码界面、编程开发元素、金融行情元素或产品发布会视觉。"
            "四层背景：底层是暗夜卧室、床铺、枕头、窗帘、低照度房间或抽象睡眠空间；"
            "中层是睡眠波形、红色心电线、闹钟、睡眠时长标识、不可读的医学风险卡片；"
            "上层是红橙健康警示光、柔和体积光、暗部颗粒、边缘轮廓光；"
            "最上层主视觉必须是睡眠/健康风险符号，如床铺剪影、闹钟、心电图、心脏警示、身体报警光效。"
            "整体像高级健康科普栏目封面或医学科普海报，紧张但克制，不像工具软件教程、金融内容或产品发布会。"
        )
    if language == "zh" and is_gold_finance_source(source):
        return (
            "采用高冲击财经知识封面：全出血画面，不要白边和内框；"
            "画面必须只属于黄金、财富信用、央行储备和硬通货题材，不使用无关数码界面、无关软件界面或廉价暴富海报套路。"
            "四层背景：底层是深黑金库、暗色金融地图、央行金库门或抽象全球货币空间；"
            "中层是金条堆叠、金币、熔化黄金、不可读的储备比例卡片、全球货币弧线和资产配置图形；"
            "上层是金属反射、暖金体积光、金币粒子、边缘轮廓光和少量红色风险提示；"
            "最上层主视觉必须是高质感 999 金条、金库、金币、信用锚符号或全球储备网络。"
            "整体像高级财经知识栏目封面或商业纪录片海报，硬核、克制、有财富质感，避免无关软件截图感。"
        )
    if language == "zh" and is_food_documentary_source(source):
        # 美食封面走「电影海报式纪录片封面」范式：纯黑暗调底 + 粉笔喷溅大字 + 美食实拍 + 红色印章/角标 + 创作者水印
        return (
            "采用电影海报式美食纪录片封面范式：纯黑或深炭黑暗调背景（critical：单纯净色，不要四层背景、不要网格、不要电路纹理、不要梯度光斑）；"
            "画面只有 2 个独立的视觉区——上方 0-45% 文字层级（左上印章 + 多行竖向粉笔喷溅大字主标题 + 右上系列角标）+ 下方 50-95% 美食特写实拍主体；"
            "底部 5% 留账号水印。"
            "整体气质参考舌尖上的中国、料理人、Chef's Table 等纪录片单帧封面——电影感低调照明、强焦点光、暗色背景、食物质感真实可见、暖色高光、深褐色阴影。"
            "字体气质 critical：主标题必须是**粉笔颗粒感 + 墨迹喷溅 + 撕裂残破边缘 + 旧报纸标题感**的厚重大字，"
            "**绝不允许 3D 立体厚切、不允许金属拼装、不允许螺丝铆钉**（那是工程教学的字体）。"
            "红色仅用于左上品牌印章和右上小角标（高饱和暖红 #C92A2A），不要大面积红色。"
            "重要：宁可元素少、留白多，也不要把画面塞满；'电影海报感'是这类纪录片封面的灵魂。"
        )
    if language == "zh" and is_academic_engineering_source(source):
        # 学科教育走极简主义工程科普海报范式：少量元素、强层级、留白、高对比。
        # 关键是「疏密关系」——绝不能像 AI 工具模板那样塞四层背景。
        return (
            "采用极简主义工程科普海报范式：深邃的深蓝色纯净背景，没有四层背景、没有底层纹理网格、没有中层模糊 UI 卡片、没有上层粒子光效；"
            "画面只有两个独立的视觉区——上方文字层级（4 段文字结构）+ 下方工程结构主体（占 60%），中间有干净的留白呼吸感。"
            "整体气质参考极简主义海报（Bauhaus 工程图纸 + 现代信息设计），高对比度、强视觉层级、画面疏密有致；"
            "光影只用：顶部冷调轮廓光勾边 + 正面均匀漫反射，让立体标题和色块产生轻微悬浮投影；"
            "绝对不要：cyberpunk 霓虹、青色科技体积光、漂浮全息卡片、节点网络、代码光带、产品发布会感。"
            "重要：宁可元素少、留白多，也不要把画面塞满；'极简主义'是这类教学海报的灵魂。"
        )
    if language == "zh" and is_ai_tool_versus_source(source):
        return (
            "采用干净高级的'AI 工具对决'封面范式：全出血画面，不要白边内框；"
            "纯深炭黑背景（critical：单纯净暗底，不要四层背景、不要网格电路、不要梯度光斑乱光）；"
            "画面只有 2 个视觉区——上方标题区（粗黑超粗无衬线大字）+ 中下方左右两个工具符号对撞 + 中间发光对决能量裂缝；"
            "金属玻璃质感、边缘轮廓光、火花在裂缝处迸发；左暖色右冷色形成强对比对决感。"
            "整体像两个开发者工具的巅峰对决海报，干净、冷峻、张力强；"
            "绝不要 cyberpunk 霓虹乱光、不要 Claude 账号封禁元素、不要单品发布会棚拍、不要 K 线。"
            "重要：宁可元素少、留白干净，也不要把画面塞满。"
        )
    if language == "zh" and is_digital_review_source(source):
        return (
            "采用干净数码产品测评封面范式：纯黑或深炭黑摄影棚暗底（critical：单纯净色，不要四层背景、不要网格电路、不要梯度光斑）；"
            "画面只有 2 个独立视觉区——上方标题区（粗黑硬朗无衬线大字，产品名/卖点）+ 中下产品 3D 棚拍特写；"
            "产品有真实金属/玻璃质感、边缘反光、轮廓光、轻微悬浮投影，像产品发布会主视觉或数码评测栏目封面；"
            "冷色调高级感（银/香槟金/紫/白），干净、冷峻、留白。"
            "绝对不要：cyberpunk 霓虹、AI 节点网络、K 线、代码终端、四层背景、学科教材立体字、真人/假人脸。"
            "重要：产品是唯一主体，画面干净高级，不堆砌元素。"
        )
    palette_rules = palette_direction(title, analysis, language)
    return (
        f"采用高冲击科技封面：全出血画面，不要白边和内框；{palette_rules}"
        "四层背景：底层细密网格和电路纹理；中层模糊的浏览器窗口、代码面板、AI 节点关系图，保持不可读；"
        "上层体积光、粒子、边缘辉光和反射；最上层主视觉必须有材质感、金属或玻璃质感、轮廓光。"
        "画面要像高端 AI 产品发布会海报或开发者工具爆款封面，锐利、昂贵、信息密度高。"
    )


# 中文生僻字字形提示：Seedream 等中文生图模型对低频字鲁棒性差，容易写成形近字。
# 命中即在 prompt 末尾追加字形描述，引导模型写对。
RARE_CHAR_HINTS = {
    "桁": "「桁」字的写法是木字旁（左边）加'行'字（右边），不要写成'析'、'梁'、'横'、'樯'或其他形近字",
    "玑": "「玑」字的写法是王字旁/斜玉旁（左边）加'几'字（右边），不要写成'现'、'机'、'矶'、'玑'以外的形近字",
    "弦": "「弦」字的写法是弓字旁（左边）加'玄'字（右边），不要写成'玹'或形近字",
    "矩": "「矩」字的写法是矢字旁（左边）加'巨'字（右边），不要写成'短'或形近字",
    "杆": "「杆」字的写法是木字旁（左边）加'干'字（右边），不要写成'秆'或形近字",
    "簧": "「簧」字的写法是上面竹字头，下面'黄'字，不要写成'横'或形近字",
    "桁架": "「桁架」整词必须写正确，'桁'是木字旁加行字（非'析'非'梁'非'橫'），'架'是上面'加'下面'木'",
}


def rare_char_hint_for(*texts):
    """收集 texts 里出现的生僻字提示。"""
    s = "".join(str(t) for t in texts if t)
    hits = []
    seen = set()
    for char, hint in RARE_CHAR_HINTS.items():
        if char in s and char not in seen:
            seen.add(char)
            hits.append(hint)
    return hits


def parse_academic_title(title, subtitle, kicker_arg, question_arg):
    """
    把学科教育的标题拆解成 4 层文字结构：kicker / main_title / question / bottom_label。

    优先级：
    1. 如果 title 是「这样的X你喜欢吗？Y篇」这种完整 hook 格式，正则拆解。
    2. 否则用 CLI 参数 kicker_arg / question_arg。
    3. 都没有就用启发式默认值（kicker="这样的"，question="你喜欢吗？"）。
       这套默认 hook 对学科教育垂类通用——参考奥达升《结构力学》等头部账号的封面范式。
    """
    import re
    main_title = title
    bottom_label = subtitle or ""
    kicker = kicker_arg or ""
    question = question_arg or ""

    # 尝试拆解完整 hook 标题：「这样的X你喜欢吗？Y篇」「这样的X你学过吗？Y篇」等
    m = re.match(r"^(这样的|这种)?(.+?)(你喜欢吗[？?]?|你学过吗[？?]?|你会吗[？?]?|你能听懂吗[？?]?)?[，。、 ]?(.+篇)?$", title.strip())
    if m and m.group(2) and (m.group(1) or m.group(3) or m.group(4)):
        captured_kicker, captured_main, captured_q, captured_bottom = m.groups()
        if captured_kicker:
            kicker = kicker or captured_kicker
        main_title = captured_main.strip()
        if captured_q:
            question = question or captured_q.rstrip("？?") + "？"
        if captured_bottom:
            bottom_label = bottom_label or captured_bottom.strip()

    # 启发式 fallback for 学科教育
    if not kicker:
        kicker = "这样的"
    if not question:
        question = "你喜欢吗？"
    if not bottom_label:
        bottom_label = subtitle or "知识篇"

    return kicker, main_title, question, bottom_label


def text_direction(name, title, subtitle, language, text_mode, analysis=None, kicker=None, question=None, brand_stamp=None, handle=None):
    if text_mode != "model":
        raise ValueError("Only model-rendered cover text is supported in this workflow.")
    if language == "zh":
        # 美食垂类走「印章 + 多行竖向粉笔大字 + 红色角标 + 账号水印」4 段结构。
        # 参考基准：@赛博食录、@饕餮 等头部美食 IP 的电影海报式纪录片封面。
        if analysis is not None:
            source = source_text(title, analysis)
            if is_food_documentary_source(source):
                stamp = brand_stamp or "食录"
                series_label = subtitle or "完整版"
                # handle 显式传空字符串「」或省略 → 不渲染水印；否则渲染
                show_handle = handle is not None and str(handle).strip() not in ("", "none", "off")
                handle_text = (handle or "").strip()
                # title 拆成多行（每行 2-3 字），文字模式渲染时让模型自然换行堆叠
                segments = [
                    "把封面文字按结构直接渲染进画面，必须只出现以下几段文字，不要其他任何可读文字（菜单、日期、caption 都不要）：\n"
                    f"  ① 左上品牌印章「{stamp}」：高饱和暖红色（#C92A2A 到 #E03434）方形或圆角矩形小印章，"
                    "内部白色书法/印刷风格汉字，印章边缘有自然破损/磨损感（像盖章盖出来的不完整效果），"
                    "印章整体占画面垂直 5-7%，位于左上角且不超出画面 10% 安全区；\n"
                    f"  ② 主标题「{title}」：critical——**白色或近白米色的粉笔喷溅风格超大厚重大字**，"
                    "字面必须有粉笔颗粒感、墨迹喷溅、撕裂残破边缘、磨损 noise 纹理，像旧报纸标题或粉笔在黑板上写的——"
                    "**绝对不要 3D 立体厚切字、不要金属拼装感、不要螺丝铆钉钉头**（这些是工程教学的字体气质，会让画面错位）；"
                    "标题文字必须**多行竖向堆叠**排版（每行 2-3 字垂直堆叠，可以根据语义自然断行）；\n"
                    "**字号 critical（升级）**：主标题必须**占据画面绝对主视觉地位**——"
                    "字高占画面垂直 50-65%，水平方向占画面宽度 75-92%（不是 35-45% 那种克制小字），"
                    "每个汉字尺寸要**大到压住一切**、像电影海报或杂志封面巨型标题那种气势，不可"
                    "让食物主体的体量超过文字；\n"
                    f"  ③ 右上角系列角标「{series_label}」：高饱和暖红色（#C92A2A）矩形色块 + 内部纯白色无衬线粗体小字，"
                    "色块体量小巧（约画面宽度的 8-12%），位于右上角，可微向右倾斜 -3° 到 -8° 呈悬挂感，"
                    "色块下方有清晰深色投影；\n"
                ]
                if show_handle:
                    segments.append(
                        f"  ④ 底部账号水印「{handle_text}」：白色或浅米色细体无衬线小字，位于画面底部居中或左下区域，"
                        "字号克制（占画面垂直 2-3%），呈现创作者署名感，不要喧宾夺主。\n"
                    )
                else:
                    segments.append(
                        "  ④ **绝对不要**在底部或任何位置渲染创作者账号 @ 水印、签名、品牌名称——画面底部保持干净纯背景或仅露食物主体的边缘，不要出现任何 @xxx 形式的文字。\n"
                    )
                segments.append(
                    "**前后景层叠 critical（杂志封面式 z-order，这是这类封面的灵魂细节）**：\n"
                    "  ⚡ 主标题文字位于画面**后景层**（z-order 较低、靠近背景），不是漂浮在最上方的图层；\n"
                    "  ⚡ 美食主体 + 手 / 料理工具位于**前景层**（z-order 最高），并且**必须部分遮挡主标题文字的下半部或局部笔画**——"
                    "例如手伸进画面托起寿司时，手的手指、手背、寿司本身要**自然遮挡掉主标题最后一行（如「贵」字）的下半部分**，"
                    "或者料理刷/筷子/食材横穿主标题中部，产生**深度感和层叠关系**；\n"
                    "  ⚡ 视觉效果像杂志封面 model 站在大字 logo 后面、人物头部挡住一部分文字那种经典设计——观众一眼能看出'文字在后、食物在前'的空间关系；\n"
                    "  ⚡ 主标题文字本身保持完整渲染（不要预先擦掉笔画），由前景主体自然遮盖来产生遮挡效果，"
                    "被遮挡的字仍能从未被挡部分识别出来；\n"
                    "  ⚡ 不要让主标题完全悬浮在空白区域，必须有前景主体侵入文字区域。\n"
                    "几段文字均**横排**（除③的轻微斜放），端正、无错别字、无乱码、无多余字、不可裁切；"
                    "**关键 critical**：主标题字体一定是粉笔/喷溅/撕裂质感，不是工程教学那种 3D 立体金属感——这是这类美食封面的灵魂特征。"
                )
                return "".join(segments)
        # 学科教育走 4 层文字结构（kicker + 立体大主标题 + 白色斜疑问标签 + 橙色矩形系列标签）。
        # 这是从《奥达升 AWE · 结构力学》等头部账号反推出的极简主义海报范式。
        if analysis is not None:
            source = source_text(title, analysis)
            if is_academic_engineering_source(source):
                k, mt, q, bl = parse_academic_title(title, subtitle, kicker, question)
                # 收集 4 段文字中的生僻字字形提示，附在 prompt 末尾引导模型写对
                rare_hints = rare_char_hint_for(k, mt, q, bl)
                rare_hint_text = ""
                if rare_hints:
                    rare_hint_text = (
                        "\n生僻字字形提示（必须按此正确书写，不要写成形近错字）：\n" +
                        "\n".join(f"  · {h}" for h in rare_hints)
                    )
                return (
                    "把封面文字按 4 层结构直接渲染进画面，必须只出现这 4 段文字，不要其他可读文字：\n"
                    f"  ① kicker 小字「{k}」+ 像素鼠标 icon："
                    f"位置 critical——必须在主标题「{mt}」的**左上角外侧**（也就是「{mt}」第一个字的左上方），"
                    "**不要压在主标题上方、不要压在第一个字头顶**，要有视觉间距，像独立的角标。"
                    "kicker 字体：高明度白色无衬线粗体，体量适中（占垂直 5-7%）；"
                    "鼠标 icon：紧邻 kicker 右上方的纯白色像素风格鼠标光标（像素化锯齿边缘、不是矢量平滑），与 kicker 文字接近等高，"
                    "整体形成「这样的 + 鼠标」一对独立的角标视觉单元，与主标题保持一段干净间距。\n"
                    f"  ② 顶部居中主标题「{mt}」：**白色立体厚切拼接风格大字**（critical），三维厚度饱满、字面有几何切割感；"
                    "字宽与字距 critical 要求——**每个汉字的宽度高度严格等比、字间距严格等距，像系统粗黑体（思源黑体 Heavy / 苹方 Heavy）那样整齐**，"
                    "**绝对不要某个字明显比其他字大或小，绝对不要字间距不均**，4 个字看起来像一个统一字体集；"
                    "**字面每个汉字上点缀 3-4 颗银色金属螺丝铆钉钉头细节**——critical：铆钉位置要**对称排布**，"
                    "通常分布在每个字面的左上、右上、左下、右下四角附近，不要随机散布、不要全堆在中间；"
                    "字体正面均匀漫反射受光，顶部和侧面有冷调灰阶轮廓阴影勾边，整体厚度感清晰但克制；"
                    "主标题字高占画面垂直 22-30%，在水平方向占据画面宽度的 65-85%，是整张图的视觉绝对中心；\n"
                    f"  ③ 在主标题最后一个字的**右下角偏外侧位置**叠加一个纯白色矩形色块（critical 位置——必须**完全位于主标题右半部分的下方边缘附近**，"
                    "**绝对不能与④的橙色色块在水平方向重叠**，两个色块要有清晰的水平错位或垂直错位；"
                    "色块整体向右倾斜约 -6° 到 -10°，呈悬浮式斜放设计，不是水平正放），"
                    f"色块内部生成高对比度的黑色无衬线粗体文字「{q}」，矩形色块的边缘锐利，下方有清晰深色投影（不只是淡阴影）；"
                    "色块体量小巧（约主标题字高的 30-40%），起对话呼应作用；\n"
                    f"  ④ 主标题正下方**居中偏左**放置一个**高饱和度暖橙色矩形色块**（critical 颜色：采用偏暖的橙色 #E6661C 到 #E6741C 区间，"
                    "不要偏黄橙、不要偏荧光橙、不要带渐变和反光），"
                    f"色块向右轻微倾斜约 -3° 到 -6°（critical：要有轻微斜度，不要完全水平），"
                    f"内部生成清晰的黑色粗体大字「{bl}」，"
                    "色块边缘锐利、下方有清晰深色投影；"
                    "**色块宽度严格控制在主标题宽度的 55-70%（不要 80%+），左端从主标题左侧开始，右端到主标题中后部停止，"
                    "这样右上方刚好能给③的白色斜放标签留出独立空间**——③和④两个色块在画面上形成「左下橙色 + 右上白色」的错位斜接构图。\n"
                    "4 段文字必须横排（除③④的轻微斜放外）、端正、无错别字、无乱码、无多余字、不可裁切；色块和立体文字都带清晰悬浮投影，呈现海报式分层。"
                    "整个文字层级占画面上方 35-45%，是画面的第一视觉焦点，下方留 55-65% 给工程结构主体。"
                    f"{rare_hint_text}"
                )
        generic_rare = rare_char_hint_for(title, subtitle)
        generic_rare_text = ("\n生僻字字形提示（按此正确书写，不要写成形近字）：" + "；".join(generic_rare)) if generic_rare else ""
        return (
            f"把封面文字直接设计进画面，必须只出现这些文字：主标题「{title}」，副标题「{subtitle}」。"
            "主标题占视觉层级第一，粗黑体或超粗无衬线字体，白字或金白渐变，带清晰描边和阴影，手机缩略图可读；"
            "副标题比主标题小一号但不能太小，字高约为主标题的 35-45%，手机缩略图也要读得清，作为解释视频内容的辅助信息。"
            "文字必须横排、端正、无错别字、无乱码、无多余字、不可裁切。"
            + generic_rare_text
        )
    return (
        f"Text: \"{title}\". Small text: \"{subtitle}\". Render both directly in the cover. "
        "Use bold readable sans-serif typography, strong outline, mobile-thumbnail readability, no extra text."
    )


def build_prompt(name, title, subtitle, analysis, language, text_mode, person_mode, kicker=None, question=None, brand_stamp=None, handle=None):
    variant = VARIANTS[name]
    text_rules = text_direction(name, title, subtitle, language, text_mode, analysis=analysis, kicker=kicker, question=question, brand_stamp=brand_stamp, handle=handle)
    subject_rules = subject_direction(name, title, analysis, language, person_mode)
    source = source_text(title, analysis)
    no_person = person_mode == "no-person" or "无人物" in subject_rules or "不出现任何真人" in subject_rules or "openclaw" in source
    elements = ", ".join(filtered_elements(analysis.get("key_elements", []), no_person))
    mood = analysis.get("mood", "")
    summary = analysis.get("content_summary", "")
    summary = sanitize_no_person_text(summary) if no_person else summary
    composition_rules = composition_direction(name, title, analysis, language, person_mode)
    intent_rules = intent_direction(name, title, analysis, language)
    visual_system_rules = visual_system_direction(title, analysis, language, person_mode)
    forbidden_rules = forbidden_direction(title, analysis, language, person_mode)
    if language == "zh":
        subject_text = "" if "openclaw" in source else f"主体设计：{subject_rules}"
        return (
            f"生成一张 3:4 竖版短视频封面。"
            f"视频主题：{summary}。真实主体线索：{elements}。"
            f"画面气质：{mood}。封面方向：{intent_rules}。"
            f"构图：{composition_rules}"
            f"{subject_text}"
            f"{visual_system_rules}"
            f"{text_rules}"
            f"{forbidden_rules}"
        )
    return (
        f"Premium vertical social video cover. "
        f"Video topic: {summary}. Real subject cues: {elements}. "
        f"Visual mood: {mood}. Variant: {variant['intent']}. "
        f"Composition: {variant['composition']}. "
        "Modern editorial design, dimensional lighting, crisp focal subject, tasteful contrast, "
        f"{text_rules} No watermark, no QR code, no fake platform badge."
    )


def main():
    parser = argparse.ArgumentParser(description="Build three image-generation prompts for cover variants.")
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--title-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--language", default="auto")
    parser.add_argument("--subtitle", help="Subtitle to render or reserve space for.")
    parser.add_argument("--text-mode", choices=["model"], default="model")
    parser.add_argument("--person-mode", choices=sorted(PERSON_MODES), default="auto", help="How to handle identity-critical person covers.")
    parser.add_argument("--person-reference", help="User photo or video frame to use when --person-mode is uploaded-photo or video-frame.")
    parser.add_argument("--kicker", help="Optional small uppercase text above the main title (academic-poster layout). Default: '这样的'.")
    parser.add_argument("--question", help="Optional question-tag text rendered on a white rectangle next to the title (academic-poster layout). Default: '你喜欢吗？'.")
    parser.add_argument("--brand-stamp", help="Optional red brand stamp text rendered in the top-left corner (food-documentary layout). Default: '食录'.")
    parser.add_argument("--handle", help="Optional creator @ handle rendered at the bottom (food-documentary layout). Default: '@美食纪录'.")
    args = parser.parse_args()

    analysis = json.loads(Path(args.analysis).expanduser().read_text(encoding="utf-8"))
    require_person_decision(analysis, args.person_mode, args.person_reference)
    title = Path(args.title_file).expanduser().read_text(encoding="utf-8").strip()
    if not title:
        raise SystemExit("Title file is empty.")
    language = detect_language(title, args.language)
    subtitle = args.subtitle or subtitle_from_analysis(analysis, language)
    variants = []
    for name in ["info-heavy", "visual-heavy", "balanced"]:
        variants.append({
            "name": name,
            "title": title,
            "subtitle": subtitle,
            "prompt": build_prompt(name, title, subtitle, analysis, language, args.text_mode, args.person_mode, kicker=args.kicker, question=args.question, brand_stamp=args.brand_stamp, handle=args.handle),
            "negative_prompt": "watermark, qr code, typo, wrong text, garbled text, extra text, unreadable title, fake logo, generic presenter portrait, clutter",
        })

    result = {
        "title": title,
        "subtitle": subtitle,
        "text_mode": args.text_mode,
        "person_mode": args.person_mode,
        "person_reference": args.person_reference,
        "language": language,
        "analysis": analysis,
        "variants": variants,
    }
    Path(args.output).expanduser().write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
