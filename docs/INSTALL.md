# 安装与运行环境

[返回项目首页](../README.md#快速开始)

当前 v2 位于 `agent/showcase-v2` 分支。Skill 由 Agent 执行；图像生成使用你已配置的模型账号与额度。

| Agent / 环境 | 接入方式 | 当前条件 |
| --- | --- | --- |
| **Codex** | 安装到 `~/.codex/skills/video-cover-generator` | 已有本仓库作品案例；使用环境提供的 `image_gen`，或配置 Dreamina CLI。 |
| **Claude Code** | 安装到 `~/.claude/skills/video-cover-generator` | 提供安装方式；需先配置 Dreamina CLI 并验证生图调用，完整流程待宿主实测。 |
| **其他本地 Agent** | 安装到该 Agent 的技能目录，读取 `SKILL.md` | 需能查看图片、读写文件、执行 Python/FFmpeg，并调用已配置的生图工具；接入后需验证。 |
| **豆包工作等国内 Agent / 工作流平台** | 按平台能力加载 Skill 或拆解为工作流步骤 | 待适配、待验证；需接通视频处理、确认交互、图像生成和成片检查。 |

把 `SKILL.md` 粘贴进普通聊天框只能提供设计指导；完整出图流程还需要上述工具能力。


### Codex

首次安装（目标目录应不存在）：

```bash
mkdir -p ~/.codex/skills
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

### Claude Code

```bash
mkdir -p ~/.claude/skills
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



### 已有安装如何更新

先确认安装目录是本仓库的 Git 克隆，且没有需要保留的本地修改。以 Codex 为例：

```bash
cd ~/.codex/skills/video-cover-generator
git status
git fetch origin agent/showcase-v2
git switch agent/showcase-v2
git pull --ff-only origin agent/showcase-v2
```

若已有本地修改，先保存后再更新；如果原来是手动复制安装，请保留旧目录后按首次安装步骤操作。
