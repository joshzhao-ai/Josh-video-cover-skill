---
name: video-cover-generator-eval-20260525
description: "为抖音/快手/小红书/视频号短视频生成封面的首选 skill（旧版 ai-cover-generator 的升级版）。输入一段本地视频，自动完成视频分析、3 个标题候选、3 张差异化 3:4 竖版封面（信息优先/画面优先/稳妥平衡）、用户选择最佳后再生成对应 4:3 横版，并做跨格式一致性检查与真人资产 gating。当用户提到\"封面\"\"封面图\"\"做个封面\"\"视频封面\"\"抖音封面\"\"短视频封面\"\"视频做图\"\"给视频配图\"\"生成封面\"，或上传视频文件并提到出图、配图、展示图时，必须使用这个 skill。"
---

# Video Cover Generator（2026-06-10 定版：配方直生 · 人像门 · 超采样筛选）

输入一条本地视频 → 产出 3 张达标的 3:4 竖版封面。本工作流由 8 条真实视频逐条打磨定版（Claude Code / Codex / 天玑 / 麻醉 / 封面设计 / iPhone拆机 / 日料 / 复古相机），用户已验收。

**生图引擎：即梦 dreamina CLI**（`~/.local/bin/dreamina`，先用 `dreamina user_credit` 确认已登录）。不可用时才退到文末 Legacy（Seedream API）。

## 核心铁律（违反任何一条 = 打回）

1. **配方直生，绝不垫案例库封面图**。无人路线一律 text2image 纯提示词；案例库（`references/library_tags.json`）只用于匹配校准"该走哪个配方"。历史教训：垫参考封面只有 60-70 分且内容泄漏/跨主题串味；配方直生实测 9.5。
2. **真人只来自两处**：用户上传的照片 或 视频帧。**绝不编造可辨识的假人脸**；无人路线 prompt 必须写"不要任何人物、不要人脸"。
3. **画面文字 ≤10 字主文案**（主标题+钩子），加一行小号英文装饰；不要副标题/要点列表/水印署名。
4. **字体要有设计感且多样**：艺术字/书法/复古印刷/立体描边/关键词局部异色/与画面穿插。**禁止千篇一律"整条纯色块+平铺字"**（用户点名批评过）；色块只作局部点缀。
5. **评分诚实**：按 美感/构图/冲击力 打分，"文字清晰"只是底线不是亮点。平庸的图（如黄底白字居中产品图）就是不及格，不许自评 9 分。
6. **配色跟品牌/主题走，不写死**：pipeline 的 `pick_palette` 按品牌取色（OpenAI/Codex→黑白+科技青蓝；Claude→深蓝+珊瑚橙；复古相机→暖棕橙红…）。成片色调与品牌错配（如 OpenAI 产品配 Claude 橙）= 验收不过；同组三个变体的色调也要拉开差异，避免每次出图都一个色。

## 工作流

### Step 1 · 建工作目录 + 抽帧

```bash
WORKDIR="$HOME/Desktop/video-covers/<video-stem>_$(date '+%Y%m%d_%H%M%S')"
mkdir -p "$WORKDIR"
python3 scripts/extract_frames.py --video '<video.mp4>' --output-dir "$WORKDIR/frames" --count 12
```

### Step 2 · 智能体亲自看帧，手写 analysis.json（不要跳过、不要只靠脚本）

打开查看 5-6 张帧图（间隔取，多模态读图），判断后写 `$WORKDIR/analysis.json`：

```json
{
  "name": "<视频名>",
  "vertical": "科技|科普|美食|财经|人文社科|生活记录",
  "video_type": "info_expression|object_operation|lifestyle_scene",
  "subject_strategy": "real_person_talking_head|product|hands_object|food_documentary|lifestyle_mood|no_person_symbolic|interface|scene|illustration",
  "no_person_fallback": "mood|product|food|hands|symbolic",
  "key_elements": ["3-5个具体可画的元素"],
  "content_summary": "一句话讲清视频内容",
  "hook_summary": "钩子点(揭秘/盘点/质疑/亲历…)",
  "topic": ["话题标签2-5个"],
  "has_real_person": true,
  "has_uploaded_portrait": false,
  "portrait_frame_quality": "good|poor"
}
```

判定要点（实测教训）：
- **subject_strategy 看封面该画什么，不是看视频里有什么**。口播但封面主角是产品/实物 → `product`/`hands_object`；拆解维修 → `hands_object`；美食纪录片 → `food_documentary`；相机/旅行/出片美学 → `lifestyle_mood`；人就是主角的口播 → `real_person_talking_head`。
- `has_real_person`：只要有人出镜就 true（含画中画小窗）；古装剧情还原 B-roll 不算创作者出镜。
- `no_person_fallback`：口播视频若用户选"不放人像"该走哪个无人配方（相机测评→mood，工具讲解→symbolic…）。
- `portrait_frame_quality`：帧里的人像可否用于取帧重绘。**人占画面大、正脸清晰 → good；人只是画中画小窗/占比小/糊 → poor**（如"大画面是录屏、左下角小圆窗是人"的口播就是 poor）。

### Step 3 · 人像门（真人口播必走，向用户提问 3 选 1）

`subject_strategy=real_person_talking_head` 且 `has_real_person=true` 时，**必须停下问用户**：

1. **上传人像**（推荐·效果最佳）→ 用户给照片 → `--person-mode uploaded-photo --portrait <照片>`
2. **取视频帧**（次优·免上传）→ 从 frames/ 挑一张清晰正脸帧 → `--person-mode frame-cutout --portrait <帧>`。提醒用户：人物按海报风格重绘，神似但非精确。**仅当 `portrait_frame_quality=good` 才提供此选项**；人像只是画中画小窗/占比小/低清时取帧必差 → 隐藏此选项，直接引导上传照片。
3. **不放人像** → `--person-mode no-person`（走 `no_person_fallback` 无人配方）

产品/实物操作/美食/氛围类**不问**（封面不以口播者为主角），直接 `--person-mode auto`。

### Step 4 · 标题（用户确认后再生图）

给 2-3 个候选：主标题（品牌/主体，≤6字）+ 钩子（≤6字），合计≤10字。钩子优先：质疑（凭啥这么贵）、揭秘（官方这么用/我经历了啥）、盘点（3个真相）、亲历。用户明确说全自动时才自选。

### Step 5 · 出图（配方直生 + 超采样）

```bash
python3 scripts/cover_pipeline.py \
  --analysis "$WORKDIR/analysis.json" \
  --title '<主标题>' --hook '<钩子>' \
  --person-mode <auto|uploaded-photo|frame-cutout|no-person> \
  [--portrait <人像图>] \
  --samples 2 \
  --out "$WORKDIR/covers"
```

先 `--dry-run` 看路由决策（选了哪个配方、提示词长啥样），对了再实跑。`--samples 2` = 3 款构图 × 2 张 = 6 张候选。配方一览：`style_repaint`（真人重绘·showcase 配方）/ `product_studio` / `hands_on_object` / `food_documentary` / `lifestyle_mood` / `symbolic_no_person`（内含医学/设计题材分流）。

### Step 6 · 智能体逐张读图，按验收清单筛选，只交付达标的 3 张

**验收清单**（每张逐条过，任一不过 = 淘汰）：
1. 标题大且清晰：横向占画面 ~75-90%，手机缩略图距离一眼可读
2. 标题不顶边、不被裁切，有安全边距
3. 字体有设计感（非"纯色块+平铺字"的偷懒做法）
4. 无假人脸（真人模式则核对：是垫图那个人，无明显漂移）
5. 无内容泄漏、无水印署名、无错别字
6. 美感/构图/冲击力达标——以这些为参照系：极繁敲码涂鸦（showcase）、日料毛笔字、封面设计描边艺术字；像"黄底白字居中"那种平庸图直接淘汰
7. 主体完整、色彩和谐（官方 5 步标准）
8. 配色贴品牌/主题（OpenAI≠Claude 橙），且同组变体色调有差异、不千篇一律

6 张里挑最好的 3 张，生成 base64 内嵌的交付 HTML（图+说明+推荐位），`open` 给用户。若达标不足 3 张：分析失败原因 → 微调提示词或换构图 → 只补跑缺的款（别整组重跑）。

### Step 7 · 反馈迭代

用户逐张点评后：意见是**单张问题** → 只改那张的构图句重跑；意见是**通用问题**（字体/排版/配色风格）→ 改 `cover_pipeline.py` 里的 TRIM_RULE 或对应配方函数，**把教训沉淀进代码**，再重跑。这是这套系统持续变强的飞轮，不要只改图不改规则。

### Step 8 ·（可选下游）4:3 横版 = 同配方直生，不要改造竖版图

**禁止**用旧脚本 `generate_landscape_from_cover.py` 拿 3:4 成品改造 4:3（实测会劈成"左半文字+右半画面"的拼贴，不可用）。正确做法：**用同一配方直接生 4:3**——

```bash
python3 scripts/cover_pipeline.py --analysis "$WORKDIR/analysis.json" \
  --title '<同标题>' --hook '<同钩子>' --person-mode <同竖版> [--portrait <同人像>] \
  --ratio 4:3 --samples 2 --out "$WORKDIR/covers_4x3"
```

pipeline 会自动给提示词追加横版构图指令（主体中/右占半、标题顶部或左侧、同一视觉系统）。出图后同样按 Step 6 清单读图筛选。

## 深挖资料（references/）

- `portrait_gate_and_typography.md` — 人像门 3 选项全文 + 取帧转正依据 + 字体规则来历
- `SHOWCASE_winning_prompt.md` — showcase 级风格化重绘配方复盘（可直接套用的模板）
- `style_repaint_recipe.md` / `aesthetic_3_tricks.md` — 融合模式演化史 + 美感三招
- `cover_generation_SOP.md` — 完整 SOP（含垫图为何降级为可选增强的全过程）
- `douyin_cover_standard.md` — 官方平台红线（≤10字/无假脸/完整明亮/色彩和谐）
- `library_tags.json` — 36 张案例标签（匹配校准用，**不垫图**）

## Legacy（仅当 dreamina CLI 不可用时）

旧基线为 Seedream API 路线：`scripts/run_cover_workflow.py --video '<video.mp4>'`（需 VCG_VLM_API_KEY / VCG_IMAGE_API_KEY，Doubao Seedream，详见 `references/openclaw_seedream_text_workflow.md` 与各 checklist）。其分析/抽帧/横版/一致性脚本仍被新工作流复用；其"无参考裸生成标题必小"等旧结论已被新排版铁律取代，以本文档为准。
