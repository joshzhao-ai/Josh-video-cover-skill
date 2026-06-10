# 封面系统 Scale 验收简报 2026-05-19

## 当前目标

让输入视频后生成的封面在规模化时保持稳定：

- 3:4 竖版封面好看、标题强、有点击欲望。
- 4:3 横版封面不是硬扩图，而是重新横版构图。
- 同一个视频的 3:4 与 4:3 保持主体、标题、色彩和视觉元素一致。
- 真人强相关视频不能生成 AI 假人像，必须先选择人物策略。

## 已完成能力

### 1. Seedream 文本封面基线

已把效果较好的 `seedream.text` 路线固化到 skill：

- VLM 分析视频内容。
- 生成 3 个标题候选和副标题。
- Seedream 同时生成画面和标题文字，不走本地叠字。
- 默认输出 `info-heavy`、`visual-heavy`、`balanced` 三张 3:4 封面。
- 每次保留 `analysis.json`、`titles.json`、`prompts.seedream.text.json`、`quality.seedream.text.json` 和 review 页面。

代表产物：

- `/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260518_201532/review.seedream.text.html`
- `/Users/bytedance/Desktop/video-covers/抖音2026518-001588_20260518_223105/review.seedream.text.html`

### 2. 4:3 横版二段电路

已增加 3:4 到 4:3 的下游脚本：

- `scripts/generate_landscape_from_cover.py`
- 输入选中的 3:4 封面。
- 可选输入优秀横版参考图 `--layout-reference`。
- 默认用 `reference-mega-title` 横版骨架：超大标题、清晰副标题标签、40-60% 主体锚点、横向延展背景。
- 支持 `--subject-description` 和 `--style-description`，避免写死 OpenClaw 元素。

代表产物：

- `/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260518_201532/landscape-4x3-v4/landscape.jpg`
- `/Users/bytedance/Desktop/video-covers/抖音2026518-001588_20260518_223105/landscape-4x3/landscape.jpg`

验证结果：

- OpenClaw 横版输出为 `1440x1080`。
- 抖音 AI 认知视频横版输出为 `1440x1080`。
- 横版标题已从“小字硬扩”改成第一视觉焦点。

### 3. 真人身份门控

已新增真人资产决策门：

- `scripts/person_asset_gate.py`

它在 VLM 分析后运行。如果检测到真人强相关，会写入：

- `person_asset_gate.json`

并强制流程暂停，让用户选择：

- `uploaded-photo`：上传本人照片。
- `video-frame`：用视频里的真实帧。
- `no-person`：不用真人，改成主题概念封面。

代码层也做了硬约束：

- `scripts/build_cover_prompts.py` 在真人强相关且 `--person-mode auto` 时会直接中止。
- 这样不会再悄悄生成一个 AI 假博主。

已验证样例：

- `/Users/bytedance/Desktop/video-covers/抖音2026518-001588_20260518_223105/person_asset_gate.json`

结果：

- `requires_decision=true`
- `risk=identity-critical-person`
- 未传 `--person-mode` 时，提示词生成中止。
- 传 `--person-mode no-person` 时，提示词明确禁止人物、人脸、半身像。
- 传 `--person-mode video-frame` 时，提示词要求人物来自真实参考帧。

### 4. 用户选择点恢复

Skill 文档已改成默认不再一路跑到底：

1. 分析视频。
2. 真人强相关时先问人物策略。
3. 展示标题候选，让用户选标题。
4. 生成三张 3:4。
5. 让用户选 3:4。
6. 再生成 4:3。

只有用户明确说“全自动跑完”“你来选”时，才自动推进。

## 已补评估用例

`evals/evals.json` 现在包含 4 类测试：

- OpenClaw 基线复跑。
- Claude Code 风险钩子迁移。
- 缺少 API key 时干净停止。
- 真人强相关视频必须触发身份门控。

本地验证：

- 关键 Python 脚本 `py_compile` 通过。
- `evals/evals.json` JSON 格式校验通过。
- 最新真人视频样例的门控逻辑通过。

## 当前主要风险

### 1. 真人照片一致性仍依赖生图模型

即使传了本人照片，Seedream 仍可能把人脸“精修重绘”。这比纯 AI 假人像好，但还不是严格保真。

更稳的产品分支是：

- 真人抠图或人像裁切。
- AI 只生成背景、氛围、图形和标题。
- 最后用确定性排版合成。

但这会重新引入本地合成和文字排版，和当前“文字由模型直接画进图里”的路线有冲突，需要单独决策。

### 2. 标题文字质量还需要人工复核

当前质检能检查文件、尺寸、比例，但不能可靠判断：

- 中文有没有错字。
- 标题是否完整。
- 标题是否真的足够吸引点击。

建议后续加一个 VLM 二次审稿：

- 读图识别标题。
- 判断标题是否错字/乱码/被裁切。
- 给点击力和可读性打分。

### 3. 横竖版一致性还缺自动评分

目前横版脚本已经能继承主体和风格，但还没有自动检查：

- 标题是否一致。
- 主体是否一致。
- 色彩是否一致。
- 横版是否像真正横版封面。

建议加一个 `check_cross_format_consistency.py`，输出横竖版一致性评分。

## 下一步建议

优先级从高到低：

1. 做 VLM 质检：标题识别、错字、裁切、点击力、主体识别。
2. 做横竖版一致性检查：主体、标题、色彩、构图。
3. 给真人视频增加更稳的人像合成分支，避免 Seedream 改脸。
4. 把 4:3 默认生成 2-3 个横版模板，用户从横版 review 页面里选。
5. 建一个小样本集，覆盖 AI 工具、真人口播、纯 UI、生活类视频，持续看 scale 后的稳定性。

## 验收时建议看的文件

- Skill 主流程：`/Users/bytedance/Desktop/Coding/Codex/AI封面/video-cover-generator/SKILL.md`
- 真人门控脚本：`/Users/bytedance/Desktop/Coding/Codex/AI封面/video-cover-generator/scripts/person_asset_gate.py`
- 3:4 提示词脚本：`/Users/bytedance/Desktop/Coding/Codex/AI封面/video-cover-generator/scripts/build_cover_prompts.py`
- 4:3 横版脚本：`/Users/bytedance/Desktop/Coding/Codex/AI封面/video-cover-generator/scripts/generate_landscape_from_cover.py`
- OpenClaw 横版基准：`/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260518_201532/landscape-4x3-v4/landscape.jpg`
- 真人门控样例：`/Users/bytedance/Desktop/video-covers/抖音2026518-001588_20260518_223105/person_asset_gate.json`
