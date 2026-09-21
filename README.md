<h1 align="center">Josh Video Cover Skill</h1>

<p align="center"><b>让视频的亮点，在第一眼被看见。</b></p>
<p align="center">从视频理解到横竖版封面，把创作经验变成可执行的设计流程。</p>

<p align="center">
  <img src="https://img.shields.io/badge/Codex-GPT%20Image%202-10a37f" alt="Codex / GPT Image 2">
  <img src="https://img.shields.io/badge/Dreamina-Seedream-246bfd" alt="Dreamina / Seedream">
  <img src="https://img.shields.io/badge/Output-3%3A4%20%2B%204%3A3-f59e0b" alt="3:4 竖版与 4:3 横版">
</p>

<p align="center">
  <a href="#作品先说话">真实作品与成绩</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="#同一条视频不同的生成方式">看效果对照</a> ·
  <a href="#像和设计师一起做封面">使用流程</a>
</p>

## 作品先说话

**已用于 99.1 万播放的视频；精选案例封面点击率达 49.78%。**

以下四个真实发布案例的封面，均由本 Skill 制作。

<table>
  <tr>
    <td width="25%"><a href="assets/published/codex-official-3x4.png"><img src="assets/published/codex-official-3x4.png" alt="实际发布封面：Codex 官方分享"></a></td>
    <td width="25%"><a href="assets/published/kimi-k3-3x4.png"><img src="assets/published/kimi-k3-3x4.png" alt="实际发布封面：Kimi K3 真的强，Josh 托起 Kimi 品牌物"></a></td>
    <td width="25%" align="center" valign="middle"><b>Claude 杀青了</b><br><br><sub>待补发布原图</sub></td>
    <td width="25%"><a href="assets/published/claude-vs-codex-3x4.png"><img src="assets/published/claude-vs-codex-3x4.png" alt="实际发布封面：Claude Code vs Codex"></a></td>
  </tr>
  <tr>
    <td align="center"><b>Codex 官方分享</b><br>99.1 万播放<br><b>12.43%</b> 封面点击率</td>
    <td align="center"><b>Kimi K3 真的强！</b><br>1.2 万播放<br><b>49.78%</b> 封面点击率</td>
    <td align="center"><b>Claude 杀青了</b><br>1.4 万播放<br><b>32.8%</b> 封面点击率</td>
    <td align="center"><b>Claude Code vs Codex</b><br>42.8 万播放<br><b>12.94%</b> 封面点击率</td>
  </tr>
</table>

<sub>数据来自作者提供的抖音创作者后台截图，按截图显示值记录，非实时更新。为精选作品成绩，不代表平均效果或封面的独立增量贡献。[查看后台证据与统计口径](docs/RESULTS.md)。</sub>

## 快速开始

把下面这段话发给 Codex：

```text
帮我安装视频封面 Skill：
https://github.com/joshzhao-ai/Josh-video-cover-skill
使用 agent/showcase-v2 分支，安装到 ~/.codex/skills/video-cover-generator。
检查 Python 依赖、ffmpeg、ffprobe 和图像生成工具是否可用。
如果已有安装，先检查本地修改再更新。
```

安装完成后，打开新任务，附上本地视频，说：

```text
给这个视频制作封面
```

你负责选择标题、人像和喜欢的方向；AI 负责分析视频、设计候选、检查画面和制作横竖版。无需自己编写生图提示词。

支持 Codex 的 `image_gen` 路线，以及已配置 Dreamina CLI 的 Agent 环境。[手动安装与依赖说明](#安装与运行环境)。

## 同一条视频，不同的生成方式

Skill 把标题、主体、构图、字体、配色与题材经验组织起来，再交给图像模型执行。下面用科技、美食、摄影三组案例，展示不同生成方式的实际结果。

### 科技 · 从功能界面，到创作者的主题表达

| Seedream 5.0 Lite 直出 | Seedream 5.0 Lite + Skill | GPT Image 2 + Skill |
|:---:|:---:|:---:|
| <img src="assets/comparison/codex-direct.jpg" width="240" alt="Codex 视频：Seedream 直接生成的界面式封面"> | <img src="assets/comparison/codex-seedream-skill.jpg" width="240" alt="Codex 视频：Seedream 配合 Skill 的人物动作与标题设计"> | <img src="assets/published/codex-official-3x4.png" width="240" alt="Codex 视频：GPT Image 2 配合 Skill 的真人科技封面"> |

同一主题可以组织成不同的视觉表达：人物与工具互动，或以大标题、创作者身份和内容线索建立层次。

### 美食 · 让食物质感与标题一起传达主题

| Seedream 5.0 Lite 直出 | Seedream 5.0 Lite + Skill | GPT Image 2 + Skill |
|:---:|:---:|:---:|
| <img src="assets/comparison/food-direct.jpg" width="240" alt="日料视频：Seedream 直接生成的食物与标题"> | <img src="assets/comparison/food-seedream-skill.png" width="240" alt="日料视频：Seedream 配合 Skill 的暗底食物特写与书法标题"> | <img src="assets/comparison/food-gpt-skill.png" width="240" alt="日料视频：GPT Image 2 配合 Skill 的高对比美食封面"> |

用食物的色泽、光影和摆放关系吸引目光，再用标题提出视频要回答的问题。

### 摄影 · 器材、人物与样片，各有位置

| Seedream 5.0 Lite 直出 | Seedream 5.0 Lite + Skill | GPT Image 2 + Skill |
|:---:|:---:|:---:|
| <img src="assets/comparison/camera-direct.png" width="240" alt="相机视频：Seedream 直接生成的复古相机封面"> | <img src="assets/comparison/camera-seedream-skill.png" width="240" alt="相机视频：Seedream 配合 Skill 的人物与复古器材设计"> | <img src="assets/comparison/camera-gpt-skill.png" width="240" alt="相机视频：GPT Image 2 配合 Skill 的人物、器材与样片排版"> |

根据内容，把器材外观、创作者与拍摄结果组织在一张封面里；字体和色彩也跟随摄影题材变化。

<sub>以上为作者提供的同视频效果对照，模型名称沿用原始对照图标注。文案、参考素材与构图存在差异，用于展示创作结果，不是严格控制变量的模型排名。[查看来源与完整五类对照](docs/COMPARISON.md)。</sub>

## 同一个创意，横竖都成立

以首屏的 **Codex 官方分享** 为例：竖版让标题与人物上下展开，横版重新安排为左右关系，同时延续身份、文案、配色与字体。

| 3:4 竖版 | 4:3 横版 |
|:---:|:---:|
| <img src="assets/published/codex-official-3x4.png" width="280" alt="Codex 官方分享竖版：上方标题，下方人物"> | <img src="assets/published/codex-official-4x3.png" width="490" alt="Codex 官方分享横版：左侧标题，右侧人物"> |

选定竖版后，Skill 会以该方向为依据原生生成横版，重新设计断行、景别和空间。[查看更多双尺寸作品](docs/GALLERY.md)。

## 像和设计师一起做封面

```text
你：给这个视频制作封面。 [附上视频]

AI：查看关键帧，提炼主题、亮点与内容证据。
    给出标题候选，同时询问使用上传人像、视频取帧，还是不放人像。

你：1B。 [附上人像照片，选择标题 B]

AI：生成并检查 3 张不同方向的 3:4 封面，在对话中展示。

你：选第 3 张。

AI：延续选中方向，生成并检查 2 张原生 4:3 横版候选，供你选择。
```

**一次制作，获得标题方案、三条竖版创意路线，以及选中方向的横版延展。**

### 你的内容，适合什么表达？

| 视频题材 | 设计重点 |
| --- | --- |
| AI 工具、知识口播 | 主题与点击理由、创作者身份、工具或结果物 |
| 数码、产品测评 | 产品外观、材质、使用动作与测评证据 |
| 拆机、维修、实物操作 | 手、工具与实物的关系，操作细节 |
| 美食、饮食文化 | 食物特写、光泽、热气与电影感布光 |
| 医学、知识科普 | 主题符号与核心问题的视觉解释 |
| 设计、排版教程 | 让字体、配色和版式本身成为示范 |
| 摄影、生活记录 | 器材、样片、自然光与生活氛围 |

### 支撑这些结果的四个环节

- **从视频提炼标题。** 先看内容，再找主题与点击理由；数字、成绩和强结论需要内容依据。
- **按题材设计候选。** 三条路线在构图、主视觉和表达方式上拉开差异；保留你对人像和方向的选择权。
- **分别适配模型。** GPT Image 2 明确区分身份、内容和风格参考；Dreamina 使用短中文视觉配方，并探测实际可用版本。
- **逐张检查成片。** 同时检查原图与缩略图，关注标题可读性、人物一致性、错字与肢体；失败路线定向重做。

## 安装与运行环境

当前 v2 位于 `agent/showcase-v2` 分支。需要能读取本地视频、执行 Python/FFmpeg 并调用图像生成工具的 Agent；模型调用使用你自己的账号与可用额度。

<details>
<summary><b>Codex 手动安装、Claude Code 配置与更新</b></summary>

### Codex

首次安装（目标目录应不存在）：

```bash
git clone --branch agent/showcase-v2 --single-branch \
  https://github.com/joshzhao-ai/Josh-video-cover-skill.git \
  ~/.codex/skills/video-cover-generator

python3 -m pip install -r ~/.codex/skills/video-cover-generator/scripts/requirements.txt
```

安装 FFmpeg，macOS 可使用：

```bash
brew install ffmpeg
```

其他系统请安装对应的 FFmpeg，并确保终端能运行 `ffmpeg` 和 `ffprobe`。

重新打开 Codex 任务，附上本地视频并说：

```text
给这个视频制作封面
```

环境具备 `image_gen` 时，按 Skill 默认路线调用。使用 Dreamina 路线时，可以说：

```text
用即梦给这个视频制作封面
```

<details>
<summary><b>Claude Code 安装与 Dreamina 准备</b></summary>

```bash
git clone --branch agent/showcase-v2 --single-branch \
  https://github.com/joshzhao-ai/Josh-video-cover-skill.git \
  ~/.claude/skills/video-cover-generator

python3 -m pip install -r ~/.claude/skills/video-cover-generator/scripts/requirements.txt
```

同样需要 FFmpeg。使用 Dreamina 路线前，请准备好你有权使用的 Dreamina CLI，完成登录，并验证当前环境能调用它。仓库不包含该 CLI 的安装包或模型账号。

在 Skill 目录运行能力探测：

```bash
python3 scripts/detect_dreamina_capabilities.py --requested auto
```

</details>

<details>
<summary><b>已有安装如何更新</b></summary>

先确认安装目录是本仓库的 Git 克隆，且没有需要保留的本地修改。以 Codex 为例：

```bash
cd ~/.codex/skills/video-cover-generator
git status
git fetch origin agent/showcase-v2
git switch agent/showcase-v2
git pull --ff-only origin agent/showcase-v2
```

若已有本地修改，先保存后再更新；如果原来是手动复制安装，请保留旧目录后按首次安装步骤操作。

</details>


</details>

## 常见问题

**必须上传自己的照片吗？**

有真人的视频会让你选择上传照片、使用清晰视频帧，或不放人像。清晰人像更有利于身份一致性；取帧重绘仍可能产生偏差，需要检查成片。

**需要会设计或写提示词吗？**

按对话选择标题、人像和喜欢的方向即可。你也可以补充风格偏好、必须出现的产品或希望强调的内容。

**生成后可以直接发布吗？**

工作流以可发布封面为目标，并包含逐张检查与重做。生成模型仍可能出现错字、手部异常或人物偏差，最终发布前请确认文字、身份和素材使用权限。

**能做批量测试和模型对比吗？**

仓库提供评测材料。比较时固定原视频、标题、人像、比例与路线，每次只改变一个变量，具体见 [评测协议](EVALUATION.md)。

<details>
<summary><b>开发者导航</b></summary>

| 文件 | 用途 |
| --- | --- |
| [SKILL.md](SKILL.md) | Agent 执行流程、确认节点与交付要求 |
| [标题策略](references/cover_title_strategy.md) | 主题锚点、点击理由与内容证据 |
| [风格配置](references/style_profiles.json) | 风格族及其适用条件 |
| [状态管理](scripts/cover_workflow_state.py) | 记录选择并检查关键步骤 |
| [提示词构建](scripts/codex_showcase_prompt_builder.py) | 两套模型适配策略 |
| [Dreamina 能力探测](scripts/detect_dreamina_capabilities.py) | 检测本机可用模型 |
| [评测协议](EVALUATION.md) | 流程、画面与版本回归验收 |
| [更新记录](CHANGELOG.md) | 版本变化 |

</details>

---

**用你的视频试一次。** 如果结果有值得改进的地方，欢迎[提交 Issue](https://github.com/joshzhao-ai/Josh-video-cover-skill/issues)，附上视频类型、所用模型、成片与具体问题，让下一次改进有据可依。

<p align="center"><sub>Built by Josh · Video → Idea → Cover</sub></p>
