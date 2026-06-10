# OpenClaw Seedream Text Baseline Workflow

本文档记录 `review.seedream.text.html` 这版从输入视频到输出三张封面的完整链路，并把它抽象成后续可流程化、产品化的设计。

Baseline 产物：

```text
~/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260515_152349/
  frames/
  analysis.seed.json
  titles.seed.json
  selected_title.txt
  prompts.seedream.text.json
  covers-seedream-text/
    info-heavy.jpg
    visual-heavy.jpg
    balanced.jpg
  quality.seedream.text.json
  review.seedream.text.html
```

这版的核心 recipe 可以命名为：

```text
seedream-text-openclaw-baseline-20260515
```

它的关键不是“把截图做暗再叠字”，而是让 Seedream 一次生成完整的科技封面：画面、主体、标题、副标题、光效和层次都在同一个 prompt 内完成。

## 1. 总流程

```text
输入视频
  -> 抽 12 帧
  -> VLM 分析视频内容和封面机会
  -> 生成 3 个标题候选
  -> 用户只选标题
  -> prompt builder 生成 3 条 Seedream prompt
  -> Seedream 生成 3 张封面
  -> 本地裁切/缩放到 1080x1440
  -> 基础质量检查
  -> 生成 HTML 对比页
```

实际命令形态如下：

```bash
WORKDIR="$HOME/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260515_152349"

python3 scripts/extract_frames.py \
  --video "$HOME/Downloads/Open Claw为什么爆火？ (1).mp4" \
  --output-dir "$WORKDIR/frames" \
  --count 12

python3 scripts/analyze_with_vlm.py \
  --frames-dir "$WORKDIR/frames" \
  --analysis-output "$WORKDIR/analysis.seed.json" \
  --titles-output "$WORKDIR/titles.seed.json" \
  --language zh \
  --max-frames 12

printf 'OpenClaw爆火' > "$WORKDIR/selected_title.txt"

python3 scripts/build_cover_prompts.py \
  --analysis "$WORKDIR/analysis.seed.json" \
  --title-file "$WORKDIR/selected_title.txt" \
  --output "$WORKDIR/prompts.seedream.text.json" \
  --language zh \
  --subtitle 'AI助手新范式' \
  --text-mode model

python3 scripts/generate_ai_covers.py \
  --prompts "$WORKDIR/prompts.seedream.text.json" \
  --output-dir "$WORKDIR/covers-seedream-text" \
  --reference-frame "$WORKDIR/frames/frame_01.jpg"

python3 scripts/check_quality.py \
  --covers-dir "$WORKDIR/covers-seedream-text" \
  --output "$WORKDIR/quality.seedream.text.json"

python3 scripts/generate_review_page.py \
  --workdir "$WORKDIR" \
  --covers-dir "$WORKDIR/covers-seedream-text" \
  --quality "$WORKDIR/quality.seedream.text.json" \
  --output "$WORKDIR/review.seedream.text.html"
```

## 2. 抽帧阶段

脚本：`scripts/extract_frames.py`

输入：

```text
/Users/bytedance/Downloads/Open Claw为什么爆火？ (1).mp4
```

输出：

```text
frames/frame_00.jpg ... frame_11.jpg
frames/index.json
```

这条视频时长是 `173.082s`，抽帧从 `0.5s` 开始，到接近结尾结束，均匀抽取 12 张。`index.json` 保存每张帧的时间戳，便于复盘 VLM 到底看到了哪些画面。

产品化要点：

- 抽帧数量建议保留为配置项。短视频可以 12 帧，长视频可以 18 到 24 帧。
- 抽帧不要只取开头，因为封面钩子常出现在中后段讲解。
- 后续可以加一个 contact sheet，让人工快速判断视频内容和 VLM 是否跑偏。

## 3. 视频分析阶段

脚本：`scripts/analyze_with_vlm.py`

这个阶段把视频帧变成结构化 JSON。它做三件事：

1. 识别视频类型和主体策略。
2. 抽取可用于封面的真实元素。
3. 生成封面标题候选。

### 3.1 VLM 输入

脚本会把最多 12 张 `frame_*.jpg` 缩到最长边 1024，并转成 base64 data URL，连同分析 prompt 一起发给 VLM。

当前默认 Doubao Seed responses API：

```text
VCG_VLM_API_URL=https://ark.cn-beijing.volces.com/api/v3/responses
VCG_VLM_MODEL=doubao-seed-2-0-pro-260215
VCG_VLM_API_KEY=...
```

VLM prompt 的核心要求：

- 按短视频封面编辑视角分析，不只是总结内容。
- 标题必须有点击钩子，不要只是复述视频标题。
- 科技知识类优先使用痛点、风险、反转、结果、好奇心。
- 不要发明人物。
- 输出 JSON，不输出散文。

### 3.2 OpenClaw 的分析结果

`analysis.seed.json`：

```json
{
  "video_type": "info_expression",
  "subject_strategy": "screen-or-product",
  "key_elements": [
    "OpenClaw聊天界面",
    "Excalidraw白板说明文字",
    "AI助手能力逻辑图",
    "OpenClaw浏览器标签页"
  ],
  "mood": "干货感十足的AI工具科普风格，清晰直观传递核心信息",
  "content_summary": "讲解AI工具OpenClaw爆火的底层原因，说明其作为新型可调度AI助手的核心价值、相关风险，后续将附带安装教程",
  "recommended_frame": "frames/frame_01.jpg"
}
```

这个分析决定了后续封面不走人物，不走生活方式，而走 `screen-or-product` 的科技产品符号路线。

### 3.3 标题候选

`titles.seed.json`：

```json
{
  "titles": [
    "OpenClaw爆火解析",
    "AI进入新阶段",
    "OpenClaw安装指南"
  ]
}
```

用户最终选的是：

```text
OpenClaw爆火
```

副标题由 prompt builder 根据主题补出：

```text
AI助手新范式
```

产品化要点：

- 用户只选标题，不选封面方向。
- 标题候选最好同时带 `hook_type` 和 `reason`，方便产品界面解释为什么推荐。
- 标题和副标题应该作为一个 copy pair 存储，而不是只存单标题。

## 4. Prompt 生成阶段

脚本：`scripts/build_cover_prompts.py`

输入：

```text
analysis.seed.json
selected_title.txt
subtitle: AI助手新范式
strategy: info-heavy | visual-heavy | balanced
```

输出：

```text
prompts.seedream.text.json
```

这个阶段是效果最关键的部分。它把结构化分析拼成三条 Seedream prompt，每条 prompt 都由同一套骨架组成，但策略不同。

## 5. Prompt 骨架

这版 prompt 的骨架如下：

```text
生成一张 3:4 竖版短视频封面。
视频主题：{content_summary}。
真实主体线索：{key_elements}。
画面气质：{mood}。
封面方向：{variant_intent}。
构图：{variant_composition}
采用高冲击科技封面：全出血画面，不要白边和内框；{palette}
四层背景：底层细密网格和电路纹理；中层模糊的浏览器窗口、代码面板、AI 节点关系图，保持不可读；
上层体积光、粒子、边缘辉光和反射；最上层主视觉必须有材质感、金属或玻璃质感、轮廓光。
画面要像高端 AI 产品发布会海报或开发者工具爆款封面，锐利、昂贵、信息密度高。
把封面文字直接设计进画面，必须只出现这些文字：主标题「{title}」，副标题「{subtitle}」。
主标题占视觉层级第一，粗黑体或超粗无衬线字体，白字或金白渐变，带清晰描边和阴影，手机缩略图可读；
副标题小一号，作为解释视频内容的辅助信息。
文字必须横排、端正、无错别字、无乱码、无多余字、不可裁切。
不要生成二维码、水印、平台角标、假 logo、人物半身像、箭头贴纸、emoji；背景 UI 不要有可读小字。
```

这版有效的原因在于它同时给了模型五类信息：

- 应用场景：`3:4 竖版短视频封面`
- 内容语义：视频讲 OpenClaw 爆火、新型可调度 AI 助手
- 视觉主体：红色机械钳爪、AI 调度面板、浏览器、代码、节点图
- 审美系统：深蓝黑、高饱和红、青色光、金色、四层背景
- 文字系统：主标题和副标题必须进入画面，而且限制为唯一文字

## 6. 三个封面策略

三张图不是随机变体，而是三种明确策略。

### 6.1 info-heavy

目标：标题优先，信息判断最快。

关键构图：

```text
上方 0-30% 保留标题安全区，中部用一个红色机械钳爪和半透明 AI 调度面板作为唯一主视觉，占画面 45%，强对比。
```

适合：

- 知识科普
- 工具测评
- 用户需要一眼看懂主题的场景

### 6.2 visual-heavy

目标：主视觉冲击最大。

关键构图：

```text
一个巨大的红色 3D 机械钳爪从代码终端和浏览器窗口中冲出，占画面 55%，下三分之一保留深色标题安全区。
```

适合：

- 产品发布感
- 视觉吸引优先
- 想让封面在信息流里更“炸”的场景

### 6.3 balanced

目标：标题和主体都稳。

关键构图：

```text
中央是发光 AI 助手核心和红色钳爪符号，周围环绕浏览器窗口、代码块、节点网络，占画面 45%，中下部保留标题安全区。
```

适合：

- 默认兜底
- 视频主题较复杂
- 不确定标题或主体哪一个更能吸引点击

## 7. 主体路由

OpenClaw 这版走的是关键词路由：

```python
if "openclaw" in source:
    info-heavy -> 红色机械钳爪 + 半透明 AI 调度面板
    visual-heavy -> 巨大红色 3D 机械钳爪从终端/浏览器冲出
    balanced -> 发光 AI 助手核心 + 红色钳爪符号
```

产品化时不应该只靠写死关键词。更稳的做法是把它升级成 `subject_recipe`：

```json
{
  "product": "OpenClaw",
  "visual_metaphor": "red mechanical claw",
  "supporting_elements": ["browser window", "code terminal", "AI scheduling panel", "node graph"],
  "palette": {
    "base": "deep blue black",
    "primary": "saturated red",
    "secondary": "cyan light",
    "accent": "small amount of gold"
  }
}
```

VLM 负责识别 `product` 和 `key_elements`，规则层或模型层负责生成 `visual_metaphor`。

## 8. 图片生成阶段

脚本：`scripts/generate_ai_covers.py`

默认 Seedream 配置：

```text
VCG_IMAGE_API_URL=https://ark.cn-beijing.volces.com/api/v3/images/generations
VCG_IMAGE_MODEL=doubao-seedream-5-0-260128
VCG_IMAGE_SIZE=2K
VCG_IMAGE_API_KEY=...
```

请求体核心字段：

```json
{
  "model": "doubao-seedream-5-0-260128",
  "prompt": "...",
  "sequential_image_generation": "disabled",
  "response_format": "url",
  "size": "2K",
  "stream": false,
  "watermark": false,
  "n": 1
}
```

生成后本地只做一件事：

```text
cover_crop(image) -> 1080x1440
```

它会裁切并缩放到 3:4，不做本地叠字。文字仍然是 Seedream 在画面里生成的。

## 9. 质量检查和对比页

脚本：

```text
scripts/check_quality.py
scripts/generate_review_page.py
```

当前质量检查是 MVP 级：

- 文件存在
- Pillow 能打开
- 尺寸至少 600x800
- 宽高比接近 3:4

OpenClaw 这版三张都通过：

```text
info-heavy.jpg     1080x1440  passed
visual-heavy.jpg   1080x1440  passed
balanced.jpg       1080x1440  passed
```

`review.seedream.text.html` 只是把三张图、分析摘要、标题候选和质检 JSON 放在一起，方便人工选择。

## 10. 为什么这版效果不错

这版的优势主要来自四点。

第一，主体非常具体。它不是泛泛地说“AI 科技感”，而是让模型生成红色机械钳爪、AI 调度面板、代码终端、浏览器窗口、节点关系图。

第二，配色非常稳定。深蓝黑底加高饱和红色，辅以青色光和少量金色，既有科技感，也能在信息流里跳出来。

第三，构图给了明确空间。每个策略都有标题安全区和主体占比，模型不会把标题和主体完全挤在一起。

第四，标题被当作画面设计的一部分。prompt 明确写了主标题、副标题、字体、描边、可读性和不可裁切，而不是事后本地叠字。

## 11. 产品化建议

建议把系统拆成 7 个稳定模块。

1. `VideoIngest`
   负责接收视频、建工作目录、记录原始文件和任务 ID。

2. `FrameSampler`
   负责抽帧、生成 contact sheet、记录时间戳。

3. `VideoAnalyzer`
   负责 VLM 分析，输出 `analysis.json` 和 `titles.json`。

4. `TitlePicker`
   负责让用户只选标题。未来可以允许编辑标题和副标题，但不要让用户选封面策略。

5. `PromptPlanner`
   负责把 `analysis + title + recipe` 转成三条 prompt。这里需要版本化，当前 recipe 是 `seedream-text-openclaw-baseline-20260515`。

6. `ImageGenerator`
   负责调用 Seedream，保存原图、裁切图、API 原始响应和失败原因。

7. `ReviewAndQA`
   负责质量检查、对比页、人工选择、重试和归档。

## 12. 推荐的数据结构

任务级 metadata：

```json
{
  "task_id": "openclaw_20260515_152349",
  "source_video": "...mp4",
  "recipe_id": "seedream-text-openclaw-baseline-20260515",
  "status": "review_ready",
  "selected_title": "OpenClaw爆火",
  "selected_subtitle": "AI助手新范式",
  "model": {
    "vlm": "doubao-seed-2-0-pro-260215",
    "image": "doubao-seedream-5-0-260128"
  }
}
```

Prompt recipe：

```json
{
  "id": "seedream-text-openclaw-baseline-20260515",
  "aspect": "3:4",
  "output_size": "1080x1440",
  "text_mode": "model",
  "strategies": ["info-heavy", "visual-heavy", "balanced"],
  "style": "high-impact tech cover",
  "title_system": "主标题 + 副标题, bold outlined readable typography",
  "quality_gates": ["openable", "aspect_ratio", "resolution"]
}
```

## 13. 下一步迭代方向

短期：

- 把 `recipe_id` 写入 `prompts.json` 和 review 页。
- 保存每次 Seedream 原始响应，便于排查模型问题。
- 增加一键重试单张 variant。
- 给标题候选补 `subtitle`、`hook_type`、`reason`。

中期：

- 建立视觉质检：标题是否可读、是否有乱码、是否多余文字、是否有假 logo。
- 把 `OpenClaw` 这种关键词规则升级为 `subject_recipe`。
- 给不同垂类做 recipe：AI 工具、硬件拆解、摄影器材、生活方式。
- 对每个 recipe 做小样本 A/B，对比点击感、文字准确率、主体稳定性。

长期：

- 从“生成三张封面”升级为“生成三张可解释方案”。
- 每张方案展示：标题钩子、主体理由、适用场景、风险提示。
- 建立封面质量数据集，把人工选择结果反哺标题和 prompt 生成。

## 14. 当前版本边界

这版已经适合做产品原型，但还不是完全自动化生产系统。

已稳定：

- 视频到结构化分析
- 三标题候选
- 三策略 prompt
- Seedream 图文一体生成
- 基础文件质量检查
- HTML 对比页

仍需加强：

- 中文文字是否完全无错别字，目前靠人工看 review 页。
- UI 背景是否出现乱码，目前只靠 prompt 约束。
- 主体路由仍有关键词规则，泛化到新产品需要 recipe 化。
- 质量检查还没有视觉理解层。

产品化时不要急着把所有判断都自动化。更稳的路径是先把每一步的中间产物保存完整，让人能看见系统为什么这么分析、为什么这么写 prompt、为什么这张封面被推荐。
