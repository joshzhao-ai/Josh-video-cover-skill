<h1 align="center">Josh Video Cover Skill</h1>

<p align="center"><b>把一条本地视频，变成一套表达清晰、有点击欲、跨尺寸一致的短视频封面。</b></p>

<p align="center">
  <img src="https://img.shields.io/badge/Workflow-Video%20to%20Cover-111111" alt="workflow">
  <img src="https://img.shields.io/badge/Engine-GPT%20Image%202-10a37f" alt="GPT Image 2">
  <img src="https://img.shields.io/badge/Engine-Dreamina%205.0%20Pro-246bfd" alt="Dreamina 5.0 Pro">
  <img src="https://img.shields.io/badge/Output-3%3A4%20%2B%204%3A3-f59e0b" alt="3:4 and 4:3">
  <img src="https://img.shields.io/badge/Version-2.0-e5484d" alt="version 2.0">
</p>

> 这不是一份“把标题塞进提示词”的模板。它是一条带用户确认门、双模型适配器、视觉路线分叉和缩略图质检的完整制作流程。

## 先看结果

以下均由本 Skill 的真实工作流生成，并从候选中人工选出最终版。每组 4:3 都是选中 3:4 后的原生横版续作，不是简单裁切。

### Dreamina 5.0 Pro：真人与产品互动

| 3:4 竖版 | 4:3 横版 |
|:---:|:---:|
| <img src="assets/showcase/kimi-k3-dreamina-3x4.jpg" width="300" alt="Kimi K3 Dreamina 3:4"> | <img src="assets/showcase/kimi-k3-dreamina-4x3.jpg" width="520" alt="Kimi K3 Dreamina 4:3"> |

短判断大字、真人态度、准确品牌物和明确互动动作共同完成点击钩子。横版重新设计标题占比与人物关系，同时延续服装、主色和品牌物。

### Dreamina 5.0 Pro：结果动作化

| 3:4 竖版 | 4:3 横版 |
|:---:|:---:|
| <img src="assets/showcase/ai-ppt-dreamina-3x4.jpg" width="300" alt="AI PPT Dreamina 3:4"> | <img src="assets/showcase/ai-ppt-dreamina-4x3.jpg" width="520" alt="AI PPT Dreamina 4:3"> |

不堆 UI 和能力列表，而是把“AI 做 PPT”转成一个可记住的撕纸动作。标题、人物和结果证明在缩略图里仍然成立。

### GPT Image 2：黑金知识海报

| 3:4 竖版 | 4:3 横版 |
|:---:|:---:|
| <img src="assets/showcase/skill-image2-3x4.jpg" width="300" alt="Skill Image2 3:4"> | <img src="assets/showcase/skill-image2-4x3.jpg" width="520" alt="Skill Image2 4:3"> |

主标题负责主题和冲击，副标题负责收益，笔记本只保留一层方法证据。横版重排后仍是同一 campaign，而不是竖图向两边扩画布。

### GPT Image 2：品牌化科技封面

| 3:4 竖版 | 4:3 横版 |
|:---:|:---:|
| <img src="assets/showcase/codex-image2-3x4.jpg" width="300" alt="Codex Image2 3:4"> | <img src="assets/showcase/codex-image2-4x3.jpg" width="520" alt="Codex Image2 4:3"> |

同一位创作者、同一套主题，在不同尺寸里保持身份、品牌色和字体材质，同时按横竖场景分别优化信息层级。

## 它解决什么

普通生图流程经常输在模型调用之外：标题没有任务信息、三张候选几乎一样、人物被偷偷换衣、横版只是重新生成一张相似图、成片在大图里好看但缩略图里读不清。

本 Skill 把这些问题做成流程约束：

- **标题先确认**：用“锚点 + 点击理由”同时保证主题识别和获得感，强结果必须有视频证据。
- **人像由用户决定**：上传照片、取视频帧或不放人像，与标题候选在同一条消息里一次确认。
- **三张是三条路线**：构图、主视觉、证明方式和色彩气质必须拉开，不做同一母版换姿势。
- **4:3 是原生续作**：读取用户选中的 3:4 成片，继承不可变项，再为横版重建断行、景别和空间关系。
- **缩略图才是考场**：按 3:4 的 `180x240` 和 4:3 的 `320x240` 检查标题、人物、结果物与错字。
- **默认不等评审页**：成片直接在对话中逐张展示；只有用户明确需要批量对比时才生成 HTML。

## 一条工作流，两套适配器

两套模型共享视频分析、标题、人像、英雄物、证据物与用户选择，但不共享提示词写法。

| 适配器 | 最适合 | 提示词策略 | 参考图策略 |
| --- | --- | --- | --- |
| GPT Image 2 | 追求视觉上限、复杂构图与强设计感 | 严格画面契约、参考图角色分离、路线级创意 | 身份、内容、风格分别声明职责 |
| Dreamina / Seedream | 稳定量产、模型直出与模型能力验证 | 短中文视觉配方，按题材控制构图与材质 | 默认少参考；准确品牌物和横版续作按需加入 |

Dreamina 版本不会靠文字猜测。`scripts/detect_dreamina_capabilities.py` 会先读取本机 CLI 能力；CLI 没有明确报告 Pro 时，输出也不会冒充 5.0 Pro。

## 工作流

```mermaid
flowchart LR
    A[输入本地视频] --> B[抽帧与内容分析]
    B --> C[同一条消息确认人像与标题]
    C --> D[生成三条差异化 3:4 路线]
    D --> E[逐张质检并让用户选择]
    E --> F[原生生成两张 4:3 续作]
    F --> G[缩略图质检与交付]
```

## 安装

### Codex

```bash
git clone https://github.com/joshzhao-ai/Josh-video-cover-skill.git \
  ~/.codex/skills/video-cover-generator
```

重新打开 Codex 任务后，附上本地视频并说：

```text
给这个视频制作封面
```

Codex 环境具备 `image_gen` 时默认走 GPT Image 2；需要Seedream 模型对照时，明确说“用即梦 5.0 Pro 跑一遍”。

### Claude Code

```bash
git clone https://github.com/joshzhao-ai/Josh-video-cover-skill.git \
  ~/.claude/skills/video-cover-generator
```

Claude Code 默认使用本机可用的 Dreamina / Seedream 路线。

### 本地依赖

```bash
python3 -m pip install -r scripts/requirements.txt
brew install ffmpeg
```

使用 Dreamina 时，还需要安装并登录可用的 `dreamina` CLI，并确保 `dreamina --help` 能在当前终端运行。仓库不会替用户保存账号、Cookie 或 API Key。

## 目录

```text
SKILL.md                                   主流程、状态门与质量标准
scripts/cover_workflow_state.py           防跳步状态机
scripts/codex_showcase_prompt_builder.py  双模型请求与提示词构建
scripts/detect_dreamina_capabilities.py   Dreamina 能力探测
scripts/execute_dreamina_manifest.py      按 manifest 执行即梦请求
references/cover_title_strategy.md         标题策略
references/style_profiles.json            已验证风格族
assets/style_references/                  同比例风格参考
assets/showcase/                          本页最终案例
evals/                                    回归评测样例
```

## 质量边界

- 取视频帧做人像属于风格化重绘，神似但不保证身份完全准确；高要求请上传清晰本人照片。
- 生图模型仍可能写错生僻字或产生手部问题。Skill 的策略是逐路线质检并定向重做，不把失败图混入交付。
- 官方 Logo、产品外观和强结果数据必须来自当前视频或官方素材，不能从参考封面借用。
- 模型版本、参考图和最终人工选择都会影响结果。对比模型时应固定视频、文案、人像、比例与路线，只改变一个变量。

完整验收方式见 [EVALUATION.md](EVALUATION.md)，版本变化见 [CHANGELOG.md](CHANGELOG.md)。

## 反馈

提交 Issue 时，请附上视频类型、选中的标题、3:4 与 4:3 成片、使用引擎，以及一句“哪里不行”。高价值反馈会被沉淀为可复现的规则或回归用例。

<p align="center"><sub>v2.0 · Built by Josh with Codex and Dreamina</sub></p>
