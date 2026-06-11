# -*- coding: utf-8 -*-
"""
一条龙封面流水线（skill 内置版，2026-06-10 由 8 条真实视频打磨定版）
输入：视频分析 json（Claude 看帧手写）→ 匹配校准 → 人像门 → 选配方 → 即梦出图（配方直生，超采样）

用法：
  python3 cover_pipeline.py --analysis <analysis.json> --title <主标题≤6字> --hook <钩子≤6字> \
      [--person-mode auto|uploaded-photo|frame-cutout|no-person] [--portrait <人像图>] \
      [--samples 2] [--out <输出目录>] [--dry-run]

核心决策（勿回退）：
  · 配方直生：无人路线 text2image 纯提示词，绝不垫案例库封面图（垫图泄漏/串味，仅 60-70 分；配方直生 9.5）
  · 真人路线 image2image 只垫【人像图】（用户上传 > 取视频帧），人物被风格化重绘
  · 人像门：真人口播类必停下问 3 选项；产品/实物/美食/氛围类不问
  · 字体多样化：艺术字/书法/描边/复古印刷，色块只作局部点缀，禁整条纯色块平铺
"""
import json, os, argparse, subprocess, urllib.request, time

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_TAGS = os.path.join(SKILL_DIR, "references", "library_tags.json")
DREAMINA = os.path.expanduser("~/.local/bin/dreamina")

# ---------------- 阶段1：匹配（案例库仅作经验校准，不垫图） ----------------
BASE_SUBJ = {"实物", "界面图示", "场景", "插画"}
COMPAT = {
    "product": {"实物", "界面图示"}, "interface": {"界面图示", "实物"},
    "scene": {"场景"}, "illustration": {"插画"},
    "hands_object": {"实物", "界面图示", "场景"},
    "food_documentary": {"实物", "场景"},
    "lifestyle_mood": {"实物", "场景"},
    "no_person_symbolic": set(BASE_SUBJ),
    "real_person_talking_head": {"真人"} | BASE_SUBJ,
}
PRIMARY = {"product": "实物", "interface": "界面图示", "scene": "场景", "illustration": "插画",
           "hands_object": "实物", "food_documentary": "实物", "lifestyle_mood": "实物",
           "real_person_talking_head": "真人", "no_person_symbolic": "界面图示"}

def match(video, tags_path):
    try:
        lib = json.load(open(tags_path, encoding="utf-8"))
    except Exception:
        return []
    covers = []
    for v, arr in lib.items():
        if v == "_meta": continue
        for c in arr:
            c = dict(c); c["vertical"] = v; covers.append(c)
    strat = video["subject_strategy"]
    allow_realface = bool(video.get("has_real_person")) and bool(video.get("has_uploaded_portrait"))
    comp = COMPAT.get(strat, set(BASE_SUBJ) | {"真人"})
    primary = PRIMARY.get(strat, "实物")
    cands = []
    for c in covers:
        if c["person"] == "real_face" and not allow_realface: continue
        if c["subject"] not in comp: continue
        score = 0; rs = []
        if c["vertical"] == video.get("vertical"): score += 3; rs.append("同垂类+3")
        if c["subject"] == primary: score += 3; rs.append(f"主体精确[{c['subject']}]+3")
        elif c["subject"] in comp: score += 1; rs.append("主体兼容+1")
        if allow_realface and c["person"] == "real_face": score += 2; rs.append("真人↔真人IP+2")
        if (not allow_realface) and c["person"] in ("none", "hands", "illustration", "silhouette"):
            score += 1; rs.append("无真人↔无人参考+1")
        vtop, ctop = video.get("topic", []), c.get("topic", [])
        hit = [t for t in ctop if any((t in a or a in t) for a in vtop)]
        if hit: score += 2; rs.append(f"话题{hit}+2")
        cands.append({"id": c["id"], "score": score, "person": c["person"],
                      "subject": c["subject"], "note": c.get("note", ""), "reasons": rs})
    cands.sort(key=lambda x: -x["score"])
    return cands[:4]

# ---------------- 阶段2：配方路由 ----------------
TRIM_RULE = ("画面文字严格≤10字主文案：超大主标题「{title}」+「{hook}」；"
             "仅此一处主标题；底部一行小号英文做装饰小字。绝不要副标题/要点列表/项目符号/多余文字/水印署名。文字逐字正确、主次分明。"
             "【排版硬规则·必须遵守】"
             "①字号极大：主标题横向占画面宽度约75-90%，一眼可读，绝不能小或纤细；"
             "②留安全边距：标题距画面上/左/右边缘留出明显空隙，绝对不要顶到或被裁切到画面边缘；"
             "③字体要有强设计感、手段多样：优先用 艺术字/书法/复古印刷字/立体描边+材质/关键词局部异色/与画面元素穿插融合 等丰富处理，做出高级排版感(参考：毛笔大字、复古丝网印刷标题、描边异色艺术字)；"
             "③b 标题背板增强对比(深底封面尤其需要)：可用撞色实色块/斜切色带作为超大标题的背板来强化对比与冲击(如电光青蓝实色块衬白色立体描边大字、双色块错位分行)，但色块须有设计感(斜切/撕边/双色错位/与画面元素穿插)、字体本身仍要立体描边或异色；切忌毫无处理的'整条纯色块+平铺细字'(单调、设计感弱)；"
             "④清晰：靠字体本身的粗壮、描边、与背景的明暗对比来保证可读，避开高光辉光与复杂纹理。")

def pick_action(video):
    kw = " ".join(video.get("key_elements", [])) + video.get("content_summary", "")
    table = [(["编程", "代码", "coding", "claude", "codex", "终端"], "坐在发光笔记本前快速敲代码、身体前倾投入"),
             (["相机", "摄影", "拍照", "出片"], "手持复古相机对着镜头展示、表情生动"),
             (["评测", "测评", "对比", "上手"], "手持产品对着镜头讲解、表情笃定"),
             (["教学", "讲", "科普", "原理"], "站在发光知识板前讲解、手势引导"),
             (["球", "运动", "健身", "跑"], "做该运动的标志性动作、姿态张扬动感")]
    for keys, act in table:
        if any(k.lower() in kw.lower() for k in keys): return act
    return "自信看向镜头、半身特写、配合主题做一个标志性动作"

def pick_motif(video):
    kw = " ".join(video.get("key_elements", [])) + video.get("content_summary", "") + " ".join(video.get("topic", []))
    table = [(["编程", "代码", "codex", "claude", "终端", "软件"], "终端窗口、代码符号、闪电星星"),
             (["相机", "摄影", "胶片", "拍照", "出片", "镜头"], "复古相机、胶片卷、光圈、星星"),
             (["手机", "数码", "芯片"], "数码设备、图标、星星")]
    for keys, mt in table:
        if any(k.lower() in kw.lower() for k in keys): return mt
    return "与主题相关的符号元素、星星"

def pick_palette(video):
    """配色跟品牌/主题走，不写死（用户教训：Codex 是 OpenAI 的，配 Claude 珊瑚橙=品牌色错配）"""
    kw = (" ".join(video.get("key_elements", [])) + video.get("content_summary", "")
          + " ".join(video.get("topic", [])) + video.get("name", "")).lower()
    table = [(["codex", "openai", "gpt", "chatgpt", "sora"], "黑白极简+科技青蓝高光（OpenAI 品牌气质）"),
             (["claude", "anthropic"], "深蓝+珊瑚橙（Anthropic 品牌气质）"),
             (["相机", "胶片", "复古", "摄影", "出片"], "米白+暖棕+复古橙红"),
             (["医学", "麻醉", "手术", "健康"], "深青绿+警示橙+白"),
             (["美食", "日料", "餐", "厨"], "暗墨绿/纯黑+暖食物色")]
    for keys, pal in table:
        if any(k in kw for k in keys): return pal
    return "深蓝+珊瑚橙"

def pick_bg(video):
    """背景明度跟主题走（用户教训：浅灰/白底+青蓝点缀对比弱、主体浮不出来→不够炸）。
    科技/AI/品牌类用深底高对比更抓眼；复古相机/美食/摄影仍保留其暖亮底，避免误伤。"""
    kw = (" ".join(video.get("key_elements", [])) + video.get("content_summary", "")
          + " ".join(video.get("topic", [])) + video.get("name", "")).lower()
    warm_keys = ["相机", "胶片", "复古", "摄影", "出片", "美食", "日料", "餐", "厨", "旅行", "生活"]
    if any(k in kw for k in warm_keys):
        return "明亮/暖色背景打底，干净通透"
    dark_keys = ["codex", "openai", "gpt", "chatgpt", "sora", "claude", "anthropic", "ai",
                 "编程", "代码", "终端", "科技", "数码", "芯片", "效率", "软件"]
    if any(k in kw for k in dark_keys):
        return "深藏青/近黑深色背景打底、整体高对比，主体与标题在深底上强烈跳出(避免浅灰白底)"
    return "中性深色背景打底、适度高对比"

def style_repaint_prompts(video, title, hook):
    theme = video.get("content_summary", "")
    action = pick_action(video); motif = pick_motif(video); palette = pick_palette(video)
    bg = pick_bg(video)
    common = (f"大师级排版，极繁主义，半调图案，杂色，丝网印刷质感，点线面层次分布。核心主题：{theme}。"
              f"整组配色跟随品牌/主题气质：{palette}；不要使用与该品牌/主题无关的配色。"
              f"背景：{bg}。超大主标题压在撞色实色块/斜切色带背板上做强对比，标题文字白色立体描边、醒目跳出。")
    person = ("视觉风格：一个人物——直接用第一张照片里的人，写实重绘、五官长相发型精确保留本人神态(高神似度)；"
              "人物本身保持写实、不要卡通化，只对背景与排版做海报化/极繁处理，主体边缘描亮边从深底干净跳出，")
    trim = TRIM_RULE.format(title=title, hook=hook)
    return [
        ("repaint_graff", common + person + f"半写实海报风，{action}，周围环绕飞出的{motif}与少量涂鸦点缀。" + trim),
        ("repaint_retro", common + person + f"半写实复古印刷海报风（粗颗粒+套色错位），抱臂站立自信看镜头、半身占画面约一半、人物突出，身后巨大发光主题元素剪影与放射状点线面。" + trim),
        ("repaint_jump", common + person + f"半写实动感海报风，单手高举主题道具腾空跃起、姿态张扬，身边环绕{motif}与速度线，点线面分布与前两款拉开差异。" + trim),
    ]

def symbolic_prompts(video, title, hook):
    elems = "、".join(video.get("key_elements", [])[:4])
    theme = video.get("content_summary", "")
    trim = TRIM_RULE.format(title=title, hook=hook)
    topics = " ".join(video.get("topic", []))
    if any(k in topics for k in ["医学", "麻醉", "健康", "手术", "药"]):
        common = (f"现代医学科普信息海报，半调质感，干净有秩序，真实手术室冷青绿光氛围与扁平医学插画结合。"
                  f"核心主题：{theme}。画面只出现医疗符号元素（{elems}），绝对不要任何人物、不要人脸。配色：深青绿+警示橙+白。")
        return [("symbolic_a", common + "构图：核心医疗器械居中放大、有辉光，环绕医学图示。" + trim),
                ("symbolic_b", common + "构图：右侧手术室器械与监护仪场景，左侧大留白放标题，杂志感。" + trim),
                ("symbolic_c", common + "构图：等距信息拼贴铺满医疗符号，科普信息密集感。" + trim)]
    if any(k in topics for k in ["设计", "封面", "排版", "平面设计", "字体"]):
        common = (f"顶级平面设计感海报，大胆文字排版本身即主视觉，撞色色块+粗描边+局部异色高亮+半调网点+做旧纸纹+拼贴，杂志编辑感、信息层次强。"
                  f"核心主题：{theme}。画面用抽象设计元素(色块/描边大字/调色板/图层面板/网格/标注线)，绝对不要任何人物、不要人脸。配色：高饱和撞色(蓝+黄+橙+黑白)。")
        return [("design_a", common + "构图：超大主标题占据上半屏并做强烈描边与异色色块处理，下方拼贴几张小封面缩略卡。" + trim),
                ("design_b", common + "构图：左侧超大标题、右侧调色板与图层/排版工具元素拼贴，编辑设计感。" + trim),
                ("design_c", common + "构图：中央一张设计感爆棚的封面mockup卡片，四周环绕设计标注线与色卡。" + trim)]
    common = f"大师级排版，极繁主义，半调图案，丝网印刷质感，点线面层次分布。核心主题：{theme}。画面只出现主题符号元素（{elems}），不要任何人物、不要人脸。"
    return [("symbolic_a", common + "构图：核心符号居中放大、有材质感与辉光，环绕信息图示。背景（深蓝+珊瑚橙）。" + trim),
            ("symbolic_b", common + "构图：核心符号偏右、左侧大留白放标题，杂志感。背景（米白+深蓝套印）。" + trim),
            ("symbolic_c", common + "构图：等距信息拼贴铺满，秩序密集。背景（暗色+橙色高亮）。" + trim)]

def product_prompts(video, title, hook):
    elems = "、".join(video.get("key_elements", [])[:3])
    trim = TRIM_RULE.format(title=title, hook=hook)
    common = (f"纯深色影棚背景（无赛博朋克霓虹、无AI节点网、无代码终端），一件干净3D影棚实拍主体（{elems}），"
              f"金属玻璃质感+轮廓光+轻微悬浮投影，占画面45-60%，冷色高级配色（银/香槟金/紫/白）。看起来像产品发布会主视觉。不要任何人脸。")
    return [("product_a", common + "主体居中。" + trim),
            ("product_b", common + "主体偏下、顶部放超大标题。" + trim),
            ("product_c", common + "主体偏右、左侧留白放标题。" + trim)]

def hands_prompts(video, title, hook):
    elems = "、".join(video.get("key_elements", [])[:4])
    theme = video.get("content_summary", "")
    trim = TRIM_RULE.format(title=title, hook=hook)
    common = (f"真实质感的实物操作/拆解封面，微距特写，专业工作台场景，戏剧性侧光与浅景深，细节锐利。"
              f"核心主题：{theme}。画面主体是手持专业工具操作实物（{elems}），突出'手+工具+实物'的操作瞬间，绝对不要人物面部、不要人脸。")
    return [("hands_a", common + "构图：俯拍工作台全景，手与工具正在操作，零件有序铺开、秩序感强，标题压顶。" + trim),
            ("hands_b", common + "构图：微距特写工具正在操作实物的关键瞬间，浅景深，标题在一侧留白。" + trim),
            ("hands_c", common + "构图：一只手举着操作中的实物朝向镜头，前后景层叠，氛围光。标题大字。" + trim)]

def food_prompts(video, title, hook):
    elems = "、".join(video.get("key_elements", [])[:4])
    theme = video.get("content_summary", "")
    trim = TRIM_RULE.format(title=title, hook=hook)
    common = (f"电影感美食纪录片海报，纯黑/暗墨绿低调背景，食物特写微距，戏剧性低调布光、精致质感、油润光泽与热气。"
              f"核心主题：{theme}。画面主体是诱人的料理实拍（{elems}），占画面下部约50-65%，绝对不要任何人物、不要人脸。"
              f"标题用白色毛笔书法/做旧粉笔质感、力量感强。")
    return [("food_a", common + "构图：招牌菜微距特写居中偏下，纯黑底，顶部毛笔大字标题(关键词局部异色)，左上角红色方形印章。" + trim),
            ("food_b", common + "构图：一道精致主菜特写，暗墨绿底，竖排白色书法巨标题在一侧、配红色方印。" + trim),
            ("food_c", common + "构图：高级俯拍摆盘，顶部白+红做旧大字标题，电影质感。" + trim)]

def mood_prompts(video, title, hook):
    elems = "、".join(video.get("key_elements", [])[:4])
    theme = video.get("content_summary", "")
    trim = TRIM_RULE.format(title=title, hook=hook)
    common = (f"暖调电影感胶片颗粒氛围海报，复古质感，柔和自然光、光晕与漏光，生活美学、温暖怀旧、高级感。"
              f"核心主题：{theme}。画面主体是诱人的实物/场景（{elems}），浅景深氛围、质感细腻，绝对不要人物面部、不要人脸。")
    return [("mood_a", common + "构图：主体居中特写 + 暖阳光晕 + 胶片漏光，标题压顶。" + trim),
            ("mood_b", common + "构图：多件主题物件桌面俯拍摆放，生活美学，标题在上方。" + trim),
            ("mood_c", common + "构图：单件主体被窗边柔光照亮、背景虚化暖调，标题大字在一侧。" + trim)]

def _route_strat(strat, video, title, hook):
    if strat in ("hands_object", "hands"):
        return ("hands_on_object", "text2image", hands_prompts(video, title, hook))
    if strat in ("food_documentary", "food"):
        return ("food_documentary", "text2image", food_prompts(video, title, hook))
    if strat in ("lifestyle_mood", "mood"):
        return ("lifestyle_mood", "text2image", mood_prompts(video, title, hook))
    if strat in ("product", "interface"):
        return ("product_studio", "text2image", product_prompts(video, title, hook))
    return ("symbolic_no_person", "text2image", symbolic_prompts(video, title, hook))

def route(video, title, hook, person_mode="auto"):
    strat = video["subject_strategy"]
    has_real = bool(video.get("has_real_person"))
    GATE_STRATS = {"real_person_talking_head"}
    if has_real and person_mode == "auto" and strat in GATE_STRATS:
        return ("NEED_PERSON_DECISION", None, [])
    if person_mode in ("uploaded-photo", "frame-cutout"):
        return ("style_repaint", "image2image", style_repaint_prompts(video, title, hook))
    if person_mode == "no-person" and strat in GATE_STRATS:
        return _route_strat(video.get("no_person_fallback", "symbolic"), video, title, hook)
    return _route_strat(strat, video, title, hook)

# ---------------- 阶段3：即梦出图（超采样） ----------------
def dreamina(args):
    r = subprocess.run([DREAMINA] + args, capture_output=True, text=True)
    try: return json.loads(r.stdout)
    except Exception: return {"_raw": r.stdout[:300]}

def generate(api, prompts, portrait, out, samples=1, ratio="3:4"):
    os.makedirs(out, exist_ok=True)
    jobs = []
    for name, p in prompts:
        for s in range(samples):
            nm = name if samples == 1 else f"{name}_s{s+1}"
            if api == "image2image":
                o = dreamina(["image2image", "--images", portrait, f"--prompt={p}",
                              f"--ratio={ratio}", "--resolution_type=2k", "--model_version=5.0", "--poll=0"])
            else:
                o = dreamina(["text2image", f"--prompt={p}",
                              f"--ratio={ratio}", "--resolution_type=2k", "--model_version=5.0", "--poll=0"])
            print(f"  {nm} -> submit={o.get('submit_id')} {o.get('gen_status') or o.get('_raw','')}")
            jobs.append({"name": nm, "submit_id": o.get("submit_id"), "status": o.get("gen_status"), "prompt": p})
            time.sleep(0.6)
    dl = time.time() + 420
    pend = lambda: [j for j in jobs if j.get("status") not in ("success", "fail") and j.get("submit_id")]
    while pend() and time.time() < dl:
        time.sleep(6)
        for j in pend():
            o = dreamina(["query_result", f"--submit_id={j['submit_id']}"])
            st = o.get("gen_status")
            if st: j["status"] = st
            if st == "success":
                imgs = (o.get("result_json") or {}).get("images") or []
                if imgs: j["url"] = imgs[0].get("image_url"); print(f"  {j['name']} success")
            elif st == "fail":
                j["fail"] = o.get("fail_reason", ""); print(f"  {j['name']} FAIL {j['fail']}")
    for j in jobs:
        if j.get("status") == "success" and j.get("url"):
            dst = f"{out}/{j['name']}.png"; urllib.request.urlretrieve(j["url"], dst); j["file"] = dst
            print(f"  {j['name']} downloaded {os.path.getsize(dst)//1024}KB")
    json.dump(jobs, open(f"{out}/prompts.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return jobs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis", required=True)
    ap.add_argument("--portrait", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--hook", default="")
    ap.add_argument("--person-mode", default="auto", choices=["auto", "uploaded-photo", "frame-cutout", "no-person"])
    ap.add_argument("--samples", type=int, default=2, help="每个提示词出几张(超采样，默认2→共6张供筛选)")
    ap.add_argument("--ratio", default="3:4", help="3:4 竖版(默认) / 4:3 横版(同配方直生，自动追加横版构图指令)")
    ap.add_argument("--tags", default=DEFAULT_TAGS)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    video = json.load(open(a.analysis, encoding="utf-8"))
    title = a.title or video.get("name", "标题")
    hook = a.hook or video.get("hook_summary", "")
    print(f"\n=== 视频：{video.get('name')} [{video.get('vertical')} · {video['subject_strategy']}] ===")
    print(f"标题：「{title}」+「{hook}」  有真人={bool(video.get('has_real_person'))}  人像模式={a.person_mode}  超采样×{a.samples}")

    print("\n--- 阶段1 匹配校准（案例库仅校准配方方向，不垫图）---")
    for c in match(video, a.tags):
        print(f"  ✓ {c['id']} 分{c['score']} [{c['person']}/{c['subject']}] {c['note']} — {'；'.join(c['reasons'])}")

    print("\n--- 阶段2 配方路由 ---")
    mode, api, prompts = route(video, title, hook, a.person_mode)
    if mode == "NEED_PERSON_DECISION":
        pfq = video.get("portrait_frame_quality", "good")
        print("  ⛔ 检测到真人口播 → 先问用户：封面要不要放人像？")
        print("     ① 上传人像 → --person-mode uploaded-photo --portrait <用户照片>（最佳）")
        if pfq == "good":
            print("     ② 取视频帧 → --person-mode frame-cutout --portrait <清晰正脸帧>（次优·人物为风格化重绘会神似不精确）")
        else:
            print("     （视频里人像占比小/低清(如画中画小窗)，取帧效果必差 → 不提供取帧选项，请引导用户上传照片）")
        print("     ③ 不放人像 → --person-mode no-person（走 no_person_fallback 无人配方）")
        return
    print(f"  选定模式：{mode}  (即梦 {api} · {a.ratio})")
    # 横版：同配方直生 4:3，追加横版构图指令（不要拿 3:4 成品改造，会劈成左字右图）
    if a.ratio != "3:4":
        H = ("【横版构图】画面为 4:3 横版：主体放中部或右侧约占一半，标题横排在顶部或左侧留白区、依然超大醒目，"
             "保持与竖版同一视觉系统(配色/字体气质/风格)，不要把画面劈成左右两半拼贴。")
        prompts = [(n, p + H) for n, p in prompts]
    for name, p in prompts: print(f"  · {name}: {p[:80]}…")
    if a.dry_run:
        print("\n[dry-run] 决策正确则去掉 --dry-run 实跑。")
        return
    if api == "image2image" and not a.portrait:
        print("\n⚠️ 该模式需要 --portrait 人像图，中止。"); return
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.analysis)), "covers")
    print(f"\n--- 阶段3 出图（{len(prompts)}款 × {a.samples}张 · {a.ratio}）→ {out} ---")
    jobs = generate(api, prompts, a.portrait, out, a.samples, a.ratio)
    ok = [j for j in jobs if j.get("file")]
    print(f"\n--- 阶段4 交给 Claude 读图筛选 ---")
    print(f"  本轮出图 {len(ok)}/{len(jobs)} 张 → {out}")
    print("  Claude 必须逐张 Read 并按 SKILL.md 的【验收清单】筛选，只交付达标的 3 张。")

if __name__ == "__main__":
    main()
