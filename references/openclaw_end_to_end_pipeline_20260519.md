# OpenClaw 封面生成 Skill 全流程说明

本文档记录一次完整的 end-to-end 跑法：从输入视频，到生成 3:4 竖版封面，再从选中的 3:4 封面生成 4:3 横版封面。它既是这次 OpenClaw 案例的复盘，也可以作为后续讲解、汇报和继续产品化这个 skill 的流程底稿。

## 1. 这次案例的最终结果

输入视频：

`/Users/bytedance/Desktop/Open Claw为什么爆火？ (1).mp4`

工作目录：

`/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260519_172117`

最终标题：

```text
主标题：OpenClaw别乱装
副标题：用前先看风险
```

人物策略：

```text
no-person
```

这次视频里有真人讲解痕迹，但没有使用真人封面。原因是：如果直接让模型生成一个“像博主”的人物，容易变成 AI 假人像，和本人身份不一致。为了保效果和避免身份漂移，本次选择不使用真人，用 OpenClaw 的机械钳爪、AI 调度面板、代码界面作为主视觉。

最终选中的 3:4 竖版：

![最终 3:4 竖版](</Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260519_172117/covers-seedream-text/info-heavy.jpg>)

最终 4:3 横版：

![最终 4:3 横版](</Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260519_172117/landscape-4x3/landscape.jpg>)

补充判断：后续人工复盘时，用户认为历史版本 `landscape-4x3-v4` 是这个视频最好的横版审美基准。它的标题是 `OpenClaw爆火 / AI助手新范式`，标题钩子与本次 `OpenClaw别乱装 / 用前先看风险` 不同，但横版构图、主体气势、背景空间和缩略图点击感更强。

![最佳横版审美参考 v4](</Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260518_201532/landscape-4x3-v4/landscape.jpg>)

三张 3:4 候选预览：

![3:4 候选预览](</Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260519_172117/covers-seedream-text/preview.jpg>)

## 2. 一句话理解这个 skill

这个 skill 不是“把视频截图加标题”，而是一个封面生产流水线：

```text
输入视频
  -> 抽关键帧
  -> 用 VLM 理解视频内容、受众、钩子和视觉元素
  -> 生成标题候选
  -> 判断是否涉及真人身份风险
  -> 用户选择标题和人物策略
  -> 生成 3 张 3:4 封面候选
  -> 用户选择一张 3:4
  -> 基于选中的 3:4 重构 4:3 横版封面
  -> 做横竖版一致性检查
  -> 输出两个最终封面和完整报告
```

它的核心价值是把“好看的封面”拆成一组可控策略：内容理解、点击标题、人物身份门控、构图模板、图像生成、质量检查、一致性检查。

## 3. 怎么使用

普通入口：

```bash
python3 scripts/run_cover_workflow.py --video '<video.mp4>'
```

这次 OpenClaw 的实际跑法是分两段完成的。第一段先跑到真人门控，让用户选择人物策略和标题：

```bash
python3 video-cover-generator/scripts/run_cover_workflow.py \
  --video '/Users/bytedance/Desktop/Open Claw为什么爆火？ (1).mp4' \
  --stop-after gate
```

用户选择：

```text
no-person + OpenClaw别乱装
```

然后继续生成 3:4 候选：

```bash
python3 video-cover-generator/scripts/run_cover_workflow.py \
  --video '/Users/bytedance/Desktop/Open Claw为什么爆火？ (1).mp4' \
  --workdir '/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260519_172117' \
  --person-mode no-person \
  --title 'OpenClaw别乱装' \
  --subtitle '用前先看风险' \
  --stop-after review
```

用户从三张 3:4 候选里选择：

```text
info-heavy
```

最后继续生成 4:3 横版：

```bash
python3 video-cover-generator/scripts/run_cover_workflow.py \
  --video '/Users/bytedance/Desktop/Open Claw为什么爆火？ (1).mp4' \
  --workdir '/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260519_172117' \
  --person-mode no-person \
  --title 'OpenClaw别乱装' \
  --subtitle '用前先看风险' \
  --cover-variant info-heavy \
  --landscape-retries 1
```

本次生图使用的模型 endpoint：

```bash
export VCG_IMAGE_MODEL='ep-20260519174036-lq7t4'
```

## 4. 全流程拆解

### 4.1 输入视频和创建工作目录

输入是一个本地视频文件。runner 会在桌面生成一个时间戳目录，所有中间产物都落在同一个目录里，方便回溯。

本次目录：

```text
/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260519_172117
```

核心好处：

- 每次跑出来都是一个独立实验目录。
- 原始分析、提示词、图片、质检结果都在里面。
- 后面可以对比不同版本，不会覆盖旧结果。

### 4.2 抽帧

脚本：

```bash
scripts/extract_frames.py
```

本次视频时长约 `173.082s`，抽了 `12` 帧：

```text
frame_00: 0.5s
frame_01: 16.144s
frame_02: 31.788s
frame_03: 47.431s
frame_04: 63.075s
frame_05: 78.719s
frame_06: 94.363s
frame_07: 110.006s
frame_08: 125.65s
frame_09: 141.294s
frame_10: 156.938s
frame_11: 172.582s
```

产物：

```text
frames/
  frame_00.jpg
  ...
  frame_11.jpg
  index.json
```

这里的抽帧不是为了直接拿某一帧做封面，而是为了给 VLM 理解视频内容。也就是说，封面不是视频截图，而是基于视频理解后的“重设计”。

### 4.3 VLM 分析视频

脚本：

```bash
scripts/analyze_with_vlm.py
```

它会读取抽出来的 12 帧，然后输出两个文件：

```text
analysis.json
titles.json
```

本次 `analysis.json` 的关键结论：

```json
{
  "video_type": "info_expression",
  "subject_strategy": "real-person-from-frame",
  "industry": "AI效率工具/科技知识",
  "cover_archetype": "有博主实测型",
  "person_policy": "real-person-only",
  "needs_real_person_asset": true,
  "key_elements": [
    "OpenClaw官方文档界面",
    "飞书AI助手对话页",
    "白板讲解示意图",
    "AI助手能力架构图",
    "价值风险对比表"
  ],
  "content_summary": "拆解爆火的AI工具OpenClaw的本质，指出其核心意义是AI从传统问答模式升级为可实时调度执行任务的助手，同时分析其使用价值与潜在的权限、数据泄露风险",
  "hook_summary": "反转大众对OpenClaw的普遍误解，它不是普通的新AI工具，而是AI进入下一发展阶段的标志性产品，同时点明使用存在的安全风险",
  "recommended_frame": "frames/frame_01.jpg"
}
```

这一步做了几件重要的事：

- 判断视频类型是 `info_expression`，也就是知识讲解/信息表达类。
- 识别主题是 AI 效率工具和科技知识。
- 判断视频里有真人表达，所以默认不能随便生成一个陌生人。
- 抽出可用于封面的真实元素：OpenClaw 文档、飞书 AI 助手、白板、AI 架构图、风险对比表。
- 归纳点击钩子：OpenClaw 不只是新工具，而是 AI 进入可调度任务阶段，同时存在权限和数据风险。

### 4.4 生成标题候选

产物：

```text
titles.json
```

本次生成了三组标题：

```json
[
  {
    "title": "OpenClaw别乱装",
    "subtitle": "用前先看风险",
    "hook_type": "risk",
    "reason": "直接点出盲目安装使用的风险，戳中用户怕踩坑的痛点，吸引想要尝试这款工具的用户点击"
  },
  {
    "title": "AI真的变天了",
    "subtitle": "不再只是问答",
    "hook_type": "reversal",
    "reason": "打破大众对现有AI的固有认知，制造认知冲击，吸引对AI发展趋势感兴趣的用户"
  },
  {
    "title": "真的省时间吗？",
    "subtitle": "实测价值对比",
    "hook_type": "curiosity",
    "reason": "用疑问戳中效率工具用户的核心需求，引发用户对工具实际效用的好奇心，提升点击意愿"
  }
]
```

最后用户选择：

```text
OpenClaw别乱装
用前先看风险
```

为什么这个标题适合：

- 它不是中性的工具介绍，而是风险提示。
- “别乱装”比“为什么爆火”更有点击压力。
- “用前先看风险”明确承诺视频内容价值。
- 和视频里的权限、数据泄露风险分析相匹配。

### 4.5 真人身份门控

脚本：

```bash
scripts/person_asset_gate.py
```

产物：

```text
person_asset_gate.json
```

本次门控结果：

```json
{
  "requires_decision": true,
  "risk": "identity-critical-person",
  "score": 13,
  "safe_default": "no-person",
  "options": [
    {
      "id": "uploaded-photo",
      "label": "上传本人照片"
    },
    {
      "id": "no-person",
      "label": "不使用真人"
    }
  ],
  "experimental_options": [
    {
      "id": "video-frame",
      "label": "用视频帧"
    }
  ]
}
```

这个步骤是当前 skill 很重要的亮点。

它解决的问题是：很多口播视频里有博主本人。如果模型直接“画一个科技博主”，封面可能好看，但人像会变成陌生人。这对于个人 IP、真人账号、知识博主来说是致命问题。

所以这里有三种策略：

```text
uploaded-photo：用户上传本人照片，身份最稳。
no-person：不用真人，只做主题概念封面，保效果且不冒身份风险。
video-frame：实验选项，用视频帧做参考，但可能仍然重绘成陌生人。
```

本次选择：

```json
{
  "person_mode": "no-person",
  "person_reference": ""
}
```

这意味着后面的提示词会明确禁止：

```text
人物半身像
陌生主持人
AI 假人像
```

### 4.6 构建 3:4 生图提示词

脚本：

```bash
scripts/build_cover_prompts.py
```

产物：

```text
prompts.seedream.text.json
```

这个脚本把前面的分析结果、标题、人物策略合成三条不同方向的提示词：

```text
info-heavy：信息密度高，标题区域明确，适合知识科普和工具测评。
visual-heavy：视觉冲击更强，产品主体更大，更像发布海报。
balanced：标题和主体更均衡，稳定中间路线。
```

三条 prompt 共用的结构是：

```text
生成一张 3:4 竖版短视频封面。
视频主题：...
真实主体线索：...
画面气质：...
封面方向：...
构图：...
采用高冲击科技封面：...
四层背景：...
把封面文字直接设计进画面，只出现主标题和副标题。
禁止二维码、水印、假 logo、人物半身像、箭头贴纸、emoji。
```

这次最关键的提示词策略：

- 让模型直接把标题画进图里，而不是后期本地叠字。
- 用“红色机械钳爪”做 OpenClaw 的核心视觉隐喻。
- 背景使用深蓝黑科技层、代码面板、AI 节点、全息 UI。
- 明确 no-person，不允许出现人物半身像。
- 背景 UI 不要出现可读小字，避免脏乱和伪文本。

### 4.7 生成三张 3:4 候选

脚本：

```bash
scripts/generate_ai_covers.py
```

本次输出：

```text
covers-seedream-text/
  info-heavy.jpg
  visual-heavy.jpg
  balanced.jpg
  preview.jpg
```

三张图都通过基础质量检查：

```json
{
  "passed": true,
  "width": 1080,
  "height": 1440,
  "aspect_ratio": 0.75
}
```

候选预览：

![3:4 候选预览](</Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260519_172117/covers-seedream-text/preview.jpg>)

本次用户选择了：

```text
info-heavy
```

原因：

- 标题最大，缩略图可读性强。
- “别乱装 / 用前先看风险”的风险感最明确。
- 红色机械钳爪和蓝色 UI 面板足够贴合 OpenClaw。

### 4.8 从 3:4 生成 4:3 横版

脚本：

```bash
scripts/generate_landscape_from_cover.py
```

输入：

```text
选中的 3:4：covers-seedream-text/info-heavy.jpg
横版布局参考：/Users/bytedance/Desktop/OpenClaw封面_4比3 1.png
```

这里有一个非常重要的策略：4:3 不是把 3:4 硬扩图。

正确做法是：

```text
3:4 负责决定：主体是谁、颜色是什么、质感是什么、标题是什么。
4:3 参考图负责决定：横版应该如何排版、标题应该多大、主体应该占多少。
```

也就是说，横版要和竖版“像同一套封面”，但构图必须是横版原生构图。

这次后续复盘得到了一个重要结论：横版一致性不能被理解成“主体几何完全一样”，但也不能放松成“只要主题相近就行”。正确标准是：横版必须绑定它实际参考的那张 3:4 竖版图，保留同一套视觉身份。

对于 OpenClaw 这种非真人、符号型封面，核心一致性要素是：

```text
红色机械钳爪
深蓝黑科技背景
青色节点光
代码/浏览器/AI 调度界面
金白描边大标题
```

因此，竖版里紧凑的机械钳爪，在横版里可以被重构成更有压迫感的红色机械臂钳爪。只要它仍然明显来自同一张选中竖版的红色钳爪资产，并且颜色、材质、背景、标题风格都在同一系统里，就应该被视为合理一致，而不是失败。

横版提示词里明确要求：

- 画布比例 4:3。
- 不是竖版封面横向外扩。
- 主标题横跨顶部大部分宽度。
- 标题远看第一眼可读。
- 主视觉占 40-60%。
- 背景横向铺开，有宽阔感。
- 保留红色机械钳爪、深蓝科技背景、青蓝 UI。
- 允许非真人符号主体为了横版构图变得更大、更有动势、更像发布会海报主视觉。

### 4.9 横竖版一致性检查

脚本：

```bash
scripts/check_cross_format_consistency.py
```

检查维度：

```text
title_consistency：标题是否一致
subtitle_consistency：副标题是否一致
subject_consistency：主体是否一致
style_consistency：风格是否一致
landscape_composition：横版构图是否真的成立
thumbnail_legibility：缩略图是否可读
```

本次自动一致性检查最初偏向强调主体几何一致。第一次自动横版被打回，原因是：

```text
主体从紧凑双颚机械爪，跑成了多指机械臂或环形机械结构。
```

这说明一致性检查能抓到“主体漂移”的风险，但也暴露了一个问题：对非真人符号封面来说，它可能过度惩罚合理的横版重构。后面我们用更严格的几何约束生成了 manual2：

```text
只允许一个紧凑的红色双颚机械夹爪头。
不是机械手。
不是多指手掌。
不是长机械臂。
不要圆环装置。
不要三个以上爪尖。
```

加强后生成的横版通过检查：

```json
{
  "passed": true,
  "overall_score": 9.0,
  "scores": {
    "title_consistency": 10,
    "subtitle_consistency": 10,
    "subject_consistency": 9.0,
    "style_consistency": 10,
    "landscape_composition": 10,
    "thumbnail_legibility": 10
  }
}
```

但从人工审美来看，最佳横版不是这个更保守的 manual2，而是历史版本 v4：

```text
/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260518_201532/landscape-4x3-v4/landscape.jpg
```

v4 更好的原因：

- 主标题巨大，第一眼有冲击力。
- 副标题胶囊清晰，像真正的横版视频封面。
- 机械钳爪有前景压迫感，占据右侧主视觉。
- 背景横向纵深强，不像竖版硬扩。
- 保留了红色钳爪、深蓝科技、青色节点、金白标题这套身份系统。

这次复盘后的策略修正是：一致性检查应该区分“真人身份漂移”和“符号主体横版重构”。真人必须严格一致；符号型封面可以允许姿态、视角、机械结构变化，但前提是它仍然绑定选中的 3:4 竖版图，保留同一主体家族、同一材质色彩、同一背景系统和同一标题风格。

按这个新标准复测 v4，结果通过：

```json
{
  "passed": true,
  "overall_score": 9.0,
  "scores": {
    "title_consistency": 10,
    "subtitle_consistency": 10,
    "subject_consistency": 10,
    "style_consistency": 10,
    "landscape_composition": 9.0,
    "thumbnail_legibility": 10
  },
  "detected": {
    "portrait_subject": "C形红色机械爪，中间环抱蓝色发光能量球",
    "landscape_subject": "红色机械臂钳爪"
  }
}
```

复测报告：

```text
/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260518_201532/consistency.cross-format.v4-preferred.json
```

## 5. 本次所有关键产物

| 类型 | 路径 |
|---|---|
| 工作目录 | `/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260519_172117` |
| 视频分析 | `/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260519_172117/analysis.json` |
| 标题候选 | `/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260519_172117/titles.json` |
| 真人门控 | `/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260519_172117/person_asset_gate.json` |
| 3:4 提示词 | `/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260519_172117/prompts.seedream.text.json` |
| 3:4 review 页 | `/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260519_172117/review.seedream.text.html` |
| 最终 3:4 | `/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260519_172117/covers-seedream-text/info-heavy.jpg` |
| 4:3 提示词 | `/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260519_172117/landscape-4x3/landscape.prompt.json` |
| 最终 4:3 | `/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260519_172117/landscape-4x3/landscape.jpg` |
| 一致性检查 | `/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260519_172117/consistency.cross-format.json` |
| 流程报告 | `/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260519_172117/workflow_report.md` |

## 6. 实际提示词

### 6.1 3:4 info-heavy prompt

```text
生成一张 3:4 竖版短视频封面。视频主题：拆解爆火的AI工具OpenClaw的本质，指出其核心意义是AI从传统问答模式升级为可实时调度执行任务的助手，同时分析其使用价值与潜在的权限、数据泄露风险。真实主体线索：OpenClaw官方文档界面, 飞书AI助手对话页, 白板讲解示意图, AI助手能力架构图, 价值风险对比表。画面气质：硬核干货感，带有认知冲击的科技科普氛围，精准戳中AI工具用户的关注痛点。封面方向：信息密度高、标题区域明确、适合知识科普和工具测评的高级科技封面。构图：上方 0-30% 保留标题安全区，中部用一个红色机械钳爪和半透明 AI 调度面板作为唯一主视觉，占画面 45%，强对比。采用高冲击科技封面：全出血画面，不要白边和内框；深蓝黑渐变底，主色为高饱和红色，辅色为青色光和少量金色。四层背景：底层细密网格和电路纹理；中层模糊的浏览器窗口、代码面板、AI 节点关系图，保持不可读；上层体积光、粒子、边缘辉光和反射；最上层主视觉必须有材质感、金属或玻璃质感、轮廓光。画面要像高端 AI 产品发布会海报或开发者工具爆款封面，锐利、昂贵、信息密度高。把封面文字直接设计进画面，必须只出现这些文字：主标题「OpenClaw别乱装」，副标题「用前先看风险」。主标题占视觉层级第一，粗黑体或超粗无衬线字体，白字或金白渐变，带清晰描边和阴影，手机缩略图可读；副标题小一号，作为解释视频内容的辅助信息。文字必须横排、端正、无错别字、无乱码、无多余字、不可裁切。不要生成二维码、水印、平台角标、假 logo、人物半身像、箭头贴纸、emoji；背景 UI 不要有可读小字。
```

### 6.2 3:4 visual-heavy prompt

```text
生成一张 3:4 竖版短视频封面。视频主题：拆解爆火的AI工具OpenClaw的本质，指出其核心意义是AI从传统问答模式升级为可实时调度执行任务的助手，同时分析其使用价值与潜在的权限、数据泄露风险。真实主体线索：OpenClaw官方文档界面, 飞书AI助手对话页, 白板讲解示意图, AI助手能力架构图, 价值风险对比表。画面气质：硬核干货感，带有认知冲击的科技科普氛围，精准戳中AI工具用户的关注痛点。封面方向：视觉冲击强、产品主体优先、像一张高级 AI 工具发布海报。构图：一个巨大的红色 3D 机械钳爪从代码终端和浏览器窗口中冲出，占画面 55%，下三分之一保留深色标题安全区。采用高冲击科技封面：全出血画面，不要白边和内框；深蓝黑渐变底，主色为高饱和红色，辅色为青色光和少量金色。四层背景：底层细密网格和电路纹理；中层模糊的浏览器窗口、代码面板、AI 节点关系图，保持不可读；上层体积光、粒子、边缘辉光和反射；最上层主视觉必须有材质感、金属或玻璃质感、轮廓光。画面要像高端 AI 产品发布会海报或开发者工具爆款封面，锐利、昂贵、信息密度高。把封面文字直接设计进画面，必须只出现这些文字：主标题「OpenClaw别乱装」，副标题「用前先看风险」。主标题占视觉层级第一，粗黑体或超粗无衬线字体，白字或金白渐变，带清晰描边和阴影，手机缩略图可读；副标题小一号，作为解释视频内容的辅助信息。文字必须横排、端正、无错别字、无乱码、无多余字、不可裁切。不要生成二维码、水印、平台角标、假 logo、人物半身像、箭头贴纸、emoji；背景 UI 不要有可读小字。
```

### 6.3 3:4 balanced prompt

```text
生成一张 3:4 竖版短视频封面。视频主题：拆解爆火的AI工具OpenClaw的本质，指出其核心意义是AI从传统问答模式升级为可实时调度执行任务的助手，同时分析其使用价值与潜在的权限、数据泄露风险。真实主体线索：OpenClaw官方文档界面, 飞书AI助手对话页, 白板讲解示意图, AI助手能力架构图, 价值风险对比表。画面气质：硬核干货感，带有认知冲击的科技科普氛围，精准戳中AI工具用户的关注痛点。封面方向：标题和主体平衡、稳妥清晰、移动端缩略图也容易理解。构图：中央是发光 AI 助手核心和红色钳爪符号，周围环绕浏览器窗口、代码块、节点网络，占画面 45%，中下部保留标题安全区。采用高冲击科技封面：全出血画面，不要白边和内框；深蓝黑渐变底，主色为高饱和红色，辅色为青色光和少量金色。四层背景：底层细密网格和电路纹理；中层模糊的浏览器窗口、代码面板、AI 节点关系图，保持不可读；上层体积光、粒子、边缘辉光和反射；最上层主视觉必须有材质感、金属或玻璃质感、轮廓光。画面要像高端 AI 产品发布会海报或开发者工具爆款封面，锐利、昂贵、信息密度高。把封面文字直接设计进画面，必须只出现这些文字：主标题「OpenClaw别乱装」，副标题「用前先看风险」。主标题占视觉层级第一，粗黑体或超粗无衬线字体，白字或金白渐变，带清晰描边和阴影，手机缩略图可读；副标题小一号，作为解释视频内容的辅助信息。文字必须横排、端正、无错别字、无乱码、无多余字、不可裁切。不要生成二维码、水印、平台角标、假 logo、人物半身像、箭头贴纸、emoji；背景 UI 不要有可读小字。
```

### 6.4 4:3 横版最终 prompt

```text
参考图是一张左右拼接的参考板：左侧是必须继承的 3:4 选中封面，右侧是横版优秀案例。左侧决定核心元素、主视觉、色彩和质感；右侧只用于学习横版排版骨架：超大标题、清晰副标题标签、40-60% 主体锚点、横向延展背景。不要照搬右侧案例的人物、吉祥物、红色配色或具体文字，除非左侧选中封面本身也有这些元素。生成一张真正为横版视频缩略图设计的 4:3 横版封面，画布比例 4:3，横向构图，不是竖版封面横向外扩。必须严格复刻左侧 3:4 竖版中的主体类型：一个紧凑的红色双颚机械夹爪头，只有上下一对弯曲夹爪，夹爪像螃蟹钳的两片钳口；主体不是机械手，不是多指手掌，不是长机械臂，不要圆环装置，不要三个以上爪尖，不要长筒机械臂。夹爪头可以横向放大并放在右下前景，但形状必须仍然是双颚 C 形红色夹爪。背景保留蓝色全息 UI 面板、代码窗口和科技网格。严格延续竖版 info-heavy 的深蓝黑背景、青蓝全息窗口、细密电路线、金白描边标题、红色金属夹爪和青色光效；不要变成红灰背景，不要简化成普通节点图。采用优秀横版封面的骨架重新构图：顶部或左上 25-32% 画面给超大主标题，主标题整体横跨画布 70-95% 宽度，字高约占画布高度 18-26%，远看必须一眼读清。副标题做成明显的横向标签、胶囊或短横条，放在主标题下方或右侧中部，不能是角落小字。主视觉锚点占 40-60% 画面，放在中右或下方前景，可以轻微压住背景 UI，但不能挡住主标题。背景 UI、节点、代码面板只作为暗部层次，从左到右铺开，形成横版封面的宽阔感。背景必须横向铺开，有从左到右的空间层次和光效动线；左侧文字区要有干净暗背景，右侧主体区要有细节和轮廓光。文字必须由模型直接设计进画面，只出现这些文字：主标题「OpenClaw别乱装」，副标题「用前先看风险」。标题完整、不贴边、不变形、不缩小成角落小字；横版缩略图远看也要先读到标题。如果标题和主体发生冲突，优先保证标题巨大且清晰，再调整主体位置。整体像高端 AI 产品发布会横版海报或 YouTube/B站横版科技封面，图文层级强、标题大、主体大、留白有控制。禁止竖版海报式居中小标题，禁止把原图简单拉宽，禁止只在四周补背景，禁止标题小于主视觉。不要生成二维码、水印、平台角标、假 logo、无关人物或陌生主持人、箭头贴纸、emoji；背景 UI 不要有可读小字。参考图来源策略：info-heavy-manual2。主标题必须巨大清晰，横跨顶部大部分宽度；副标题用纯白或金白大字，不要灰色圆角胶囊按钮。整体要像同一张竖版封面改成横版，而不是换了新主体。
```

## 7. 这个 skill 当前的亮点

### 7.1 先理解视频，再生成封面

它不是直接拿第一帧做封面，也不是简单让模型“做一个科技感封面”。它会先分析视频，得到：

- 视频类型
- 行业
- 受众
- 内容总结
- 点击钩子
- 主视觉元素
- 是否涉及真人身份

这让提示词更像“基于内容的创意简报”，而不是随机美术描述。

### 7.2 标题是策略产物，不是随便起

标题候选会区分 risk、reversal、curiosity 等不同钩子类型。这样用户不是在三个差不多的标题里选，而是在三种点击策略里选。

本次最终选择 `OpenClaw别乱装`，就是风险型标题，和视频内容里的权限、数据泄露风险高度匹配。

### 7.3 真人身份门控很关键

这是产品化非常重要的一步。

只要视频被判断为真人强相关，流程不会直接生成一个陌生人像，而是让用户选择：

```text
上传本人照片 / 不使用真人
```

这样避免了“图很好看但不像本人”的致命问题。

### 7.4 3:4 和 4:3 是两个不同构图电路

3:4 适合短视频平台竖版封面，标题可以在上方或中下部组织。

4:3 横版必须重新设计，不能把竖版硬扩。横版要有：

- 更大的标题
- 更宽的背景空间
- 横向视觉动线
- 40-60% 的主视觉锚点
- 清晰的缩略图可读性

本次横版就是在这个逻辑下重新生成，而不是拉伸原图。

### 7.5 有自动质检和返工信号

本次第一次横版失败，质检明确指出：

```text
主体从红色机械夹爪变成了多指机械臂。
```

这个问题肉眼也能看出来，但自动质检先抓到了。之后用更强的主体约束重新生成，并通过了一致性检查。

这说明流程里已经有“自我纠错”的雏形，不只是一次性生图。

## 8. 当前仍然可以继续优化的点

### 8.1 横版主体一致性可以更自动

这次需要手动加强 prompt，才能让机械爪从多指机械臂回到双颚夹爪。

后续可以把质检失败原因自动转成更强约束，例如：

```text
如果 subject_consistency 低于 8：
  自动读取 detected.portrait_subject
  自动加入禁止项：不要变成 detected.landscape_subject
  自动要求主体几何形态保持一致
```

### 8.2 真实人物可以形成三档产品策略

当前策略已经清楚，但后续可以做成产品 UI：

```text
保真模式：上传本人照片
概念模式：不使用真人
实验模式：视频帧参考
```

默认推荐：

```text
真人强相关 -> 让用户选
非真人视频 -> 自动 no-person 或 product/screen subject
```

### 8.3 标题可加入平台风格选择

比如：

```text
知识区：更理性
抖音：更冲突
B站：更解释性
小红书：更结果导向
```

同一个视频可以生成不同平台的标题策略。

### 8.4 review 页可以升级成选择器

现在 review 页负责看图。后续可以在 review 页里直接：

- 选择 3:4 版本
- 标记标题错字
- 要求重跑某一版
- 一键进入 4:3 转换
- 展示一致性报告

## 9. 汇报时可以这样讲

可以用这段话概括：

```text
这个封面 skill 的核心不是单次生图，而是把封面生产流程产品化。
它从视频抽帧开始，用多模态模型理解内容和点击钩子，再生成标题候选。
如果检测到真人强相关，会先做人像策略门控，避免生成陌生 AI 人像。
之后基于内容分析生成三张 3:4 候选封面，让用户选择最好的竖版。
选定竖版后，再以它作为视觉身份源，重新生成 4:3 横版封面。
最后用一致性检查确认横竖版标题、主体、风格和构图是否统一。
```

## 10. 这次最终验收结论

本次 OpenClaw 案例完整跑通：

```text
输入视频：完成
抽帧：完成
视频分析：完成
标题候选：完成
真人门控：完成
no-person 策略：完成
3 张 3:4 候选：完成
用户选择 info-heavy：完成
4:3 横版生成：完成
横竖版一致性检查：通过
```

最终一致性得分：

```text
overall_score: 9.0
title_consistency: 10
subtitle_consistency: 10
subject_consistency: 9
style_consistency: 10
landscape_composition: 10
thumbnail_legibility: 10
```

最终产物：

```text
3:4 竖版：/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260519_172117/covers-seedream-text/info-heavy.jpg
4:3 横版：/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260519_172117/landscape-4x3/landscape.jpg
```

这版流程已经具备产品化雏形：它能解释自己为什么这么做，也能留下每一步的中间产物，方便复盘、调参、汇报和继续优化。
