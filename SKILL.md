---
name: video-cover-generator
description: "为抖音、快手、小红书和视频号制作视频封面。分析本地视频，确认标题和人像，默认生成两张差异化 3:4 竖版；选定后续作一张原生 4:3 横版，并检查文字、主体和缩略图。用户要求视频封面、短视频封面或给视频做封面时使用。"
---

# Video Cover Generator v2.2

目标是用更少的生成次数，交付在信息流缩略图里仍然有美感、表达清晰、值得点击的封面。

## 默认快交付：两竖一横

- **默认只生成两张 3:4 竖版，用户选定后生成一张 4:3 横版。** 不自动补第三张竖版或第二张横版；用户明确要求更多方案或对照时才增加。
- 两张竖版使用真正不同的构图；支持并行时并行生成。横版优先 `thumbnail`，同时保持选中竖版的文案、人物、主物和视觉风格，不额外制作 `faithful` 对照。
- 复用本视频已经完成的分析、参考图和确认结果；继续选图或横版阶段不重新抽帧、策划标题或重做未受影响的方案。只加载当前引擎和题材实际需要的资料，不为默认 Image 2 流程探测 Dreamina。
- 每张完成后做一次原图与缩略图检查，重点看文案准确、身份/主体稳定、无明显畸形、标题可读、无裁字。通过就立即展示，不等待其他候选或存档整理。
- 只对影响使用的错误重做该张，默认至多补一次；仍未达标时说明问题并让用户决定，不自动循环精修。不要为轻微材质、装饰或像素舍入差异重生成。
- 比例按原生目标请求；没有明确的严格上传尺寸要求时，相对比例误差 `abs((width / height) / target_ratio - 1) <= 0.002` 可接受，记录实际尺寸，不声称精确比例。明确要求严格比例时，为构建器加 `--exact-aspect-ratio`（容差为零）；指定像素尺寸还须核对实际宽高。超过阈值或违反明确规格才处理；仍禁止用裁切、拉伸、拼贴冒充原生横版。
- 单张横版通过质检后直接交付并登记为最终横版，不再强制增加一轮 A/B 选择。用户要求修改时再迭代。保留必要的 job、提示词和图片记录，不默认创建额外报告或评审页面。

## 选定后的修改

- 用户只询问设计建议时，先给判断；明确要求改图后再生成。以选中成片作为编辑参考，保留原文件，并按用户要求的数量制作对照。
- 自然神态、人物身份和整体风格优先于强行加动作。没有用户要求，不自动加“嘘”、夸张惊讶、金钱符号或底部角标。更强的手势与对比色是可测试方向，不保证更高点击率。
- 用户回到原版时，恢复该版的最终选择；若已有匹配横版，直接交付，不再生成。新候选保留为备选，不覆盖旧成片。
- 真人与原创形象组合可参考 [DeepSeek 人像案例](references/deepseek_portrait_showcase.md)；奶油白、钴蓝和蓝鲸只属于该案例，不作为所有题材的默认模板。

## 设计原则

- **一个内容决策，两套模型适配器。** 两个引擎共享用户确认的文案、人物选择、英雄物和风格方向，但各自使用已经验证的提示词结构；禁止把 Image 2 的长契约直接翻译给 Dreamina。
- **复用用户已经给出的决策。** 用户提供的明确标题、指定人像或本视频已确认的选择，直接记录并执行，不重复出候选、重新确认。只有未提供的标题/人像策略才需补问；用户明确委托全自动时可代选并如实记录。
- **横版是同一 campaign 的原生续作。** Image 2 和 Dreamina 默认都读取选中的 3:4 成片作为 `selected_vertical_reference`，继承文案、人物、英雄物、配色、字体材质和传播关系，但允许为横版重新设计机位、断行、景别与前后景。Dreamina 同时保留自己的短中文视觉配方；两者都生成原生 4:3，不裁切、拉伸或拼贴。
- **封面只传达一件事。** 一级钩子、一个大结果/证明物、一个真人或辅助证据就够了。UI、代码、网格和粒子只能做低对比氛围。
- **强结果可追溯。** 数字、收入、涨粉、权威、排名或“靠 X 达到 Y”只能来自视频、字幕、标题、用户补充或 `verified_proof`。

## 引擎策略

| 用途 | 引擎 | 规则 |
| --- | --- | --- |
| 默认主推 | Codex `image_gen` / GPT Image 2 | 使用风格参考、人物身份参考和严格的画面契约，先争取视觉上限。 |
| 稳定备选 | Dreamina / Seedream | 默认 `5.0 + 2K + recipe-direct`；共享内容决策，但使用 Dreamina 题材短配方。只在用户要求或双引擎对照时使用。 |
| 历史保底 | `scripts/cover_pipeline.py --engine dreamina` | 保留旧链路与旧 Seedream 配方，不把 Image 2 的提示词反灌进去。 |

仅在实际使用 Dreamina 时检测版本；不要猜 Seedream 版本。先运行：

```bash
python3 scripts/detect_dreamina_capabilities.py --requested auto
```

当前 CLI 没有报告 Pro 字样时，不能把泛 `5.0` 标为 `5.0 Pro`。CLI 更新并报告 Pro 模型后，适配器会自动选择它。

## 必走流程

### 1. 建目录、抽帧、分析

```bash
WORKDIR="$HOME/Desktop/video-covers/<video-stem>_$(date '+%Y%m%d_%H%M%S')"
mkdir -p "$WORKDIR/frames"
python3 scripts/extract_frames.py --video '<video.mp4>' --output-dir "$WORKDIR/frames" --count 16
python3 scripts/cover_workflow_state.py init --job "$WORKDIR/cover_job.json" --video '<video.mp4>'
```

亲自查看分散的 6-10 张帧。额外找结果展示、关键操作和清晰正脸帧。写 `$WORKDIR/analysis.json`，至少包含：

```json
{
  "content_summary": "一句话内容",
  "hook_summary": "为什么值得点开",
  "verified_proof": ["已经确认的数字、结果或事实"],
  "cover_promise": "封面承诺",
  "proof_chain": ["输入/问题", "方法", "结果"],
  "visual_proof_objects": ["一个英雄物", "一个辅助证据物"],
  "hero_object": "封面里唯一放大的准确主物",
  "evidence_object": "可选的一个辅助证据物",
  "pose_reference_frame": "完整上半身、姿态清楚的原视频帧路径",
  "content_reference_frames": ["最能证明结果的 1 张原视频帧路径"],
  "selected_style_profile": "可选风格族 id",
  "has_real_person": true,
  "portrait_frame_quality": "good|poor"
}
```

风格族只在题材和证据结构匹配时使用。相机、手机摄影或便携拍摄设备的真人实测，且视频里确实有器材与真实样片时，优先使用 `camera_review_editorial`；纯作品展示、软件教程或无样片内容不要套用。

产品、模型、AI 工具或品牌解读类视频，如果用户选择真人、有准确官方品牌物，而且标题能压缩成一个短判断/问题/收益，可选择 `creator_product_interaction`。此时 `hero_object` 必须明确写成当前官方 Logo、应用图标或产品，不能写成榜单、UI 或泛泛的“结果”；同时准备官方资产，并通过 `--content-reference '<official-asset>'` 传入。缺少这两项时 Image 2 构建器会直接拒绝生成，避免模型猜 Logo。Dreamina 需要准确品牌物时改用 `grounded`：3:4 传人像和当前官方资产；生成 4:3 时再加入用户选中的本视频 3:4 成片作为系列续作参考。不得传 GPT 成片、外部风格封面或从其他创作者封面抠出的 Logo，也不要把这套 Kimi 案例的蓝色和 Logo 复制到其他主题。

Image 2 会使用同比例风格参考；Dreamina `recipe-direct` 仍走自己的短配方，不传该参考图，现有 Seedream 规则不受影响。

再记录分析：

```bash
python3 scripts/cover_workflow_state.py record-analysis \
  --job "$WORKDIR/cover_job.json" --analysis "$WORKDIR/analysis.json"
```

### 2. 双项确认门：人像和标题一次问完

先检查本轮请求与本视频的已有选择。明确提供的标题可直接用；指定视频人像且有清晰帧时直接取帧。两项都已确定则跳过提问，使用下方命令登记；只缺一项就只问一项。需要策划标题时才读 [cover_title_strategy.md](references/cover_title_strategy.md) 并准备 3 个候选。两项都缺且 `has_real_person=true` 时，在同一条消息里同时展示两组选项：

**人像**

1. 上传人像（推荐，身份最准确）
2. 取视频帧（仅 `portrait_frame_quality=good` 时提供；会风格化重绘，神似但非精确）
3. 不放人像

**标题**

A. 稳妥清晰：锚点 + 内容范围
B. 收益承诺：锚点 + 用户收益，通常优先推荐
C. 任务型探索：锚点 + 有任务信息量的痛点/问题

每个标题候选写：标题大字、类型、锚点、理由、证据依据、证据物。不要用“别只会问 AI”这类泛情绪代替主题。最后明确提示用户一次回复组合，例如 `2B`；选择上传照片时可附图并回复 `1B`。

两项选择互不依赖，不得先问人像、等一轮回复后再问标题。视频没有真人时只展示标题。视频帧质量差时不提供取帧，或明确标为不推荐。用户只回答其中一项时，保存已确认项，只补问缺少项；选择上传但没附图时，也只补要照片，不重新问标题。

即使封面主体更像硬币、产品、实物或流程，视频有清晰真人且用户尚未选择人像策略时，仍需补齐该选择。记录已有决策或用户回复时，依次保存两项状态：

```bash
python3 scripts/cover_workflow_state.py choose-person \
  --job "$WORKDIR/cover_job.json" --mode <uploaded-photo|frame-cutout|no-person> \
  [--portrait '<face-crop>'] [--pose-reference '<original-full-frame>']
```

`portrait` 是默认身份参考。应优先保留清晰脸、帽子/发型、领口和部分肩膀；`pose-reference` 只供 Dreamina 的实验性 `grounded` 模式使用，不进入默认 `recipe-direct`。

没有真人时，直接选 `--mode auto`。用户明确说“全自动”时，可根据分析代替他做出人像和标题选择，但仍要把选择写入 job。

用户确认后记录标题：

```bash
python3 scripts/cover_workflow_state.py choose-title \
  --job "$WORKDIR/cover_job.json" \
  --title '<主题/任务>' --hook '<点击理由>' [--subtitle '<可选短承诺>']
```

标题阶段只展示一套完整候选，不额外让用户选择“创意短写”。默认两张封面都使用用户确认的完整文案。用户另外要求创意短写时，可以保留锚点压缩，但不能新增事实、数字或更强结论，并明确说明改了哪些字。用户要求文案一个字不改时禁止自动压缩。

### 3. 生成 3:4：两条视觉路线，不是同一张图换姿势

默认生成 Image 2 请求：

```bash
python3 scripts/codex_showcase_prompt_builder.py \
  --job "$WORKDIR/cover_job.json" --analysis "$WORKDIR/analysis.json" \
  --ratio 3:4 --engine image2 --out "$WORKDIR/covers_3x4"
```

构建器默认输出两条路线。可按内容用两个 `--routes '<route-id>'` 明确指定；只有用户要求增加方案时才使用 `--vertical-count 3` 或显式指定更多路线。读取 `$WORKDIR/covers_3x4/cover_requests.json`。每个 route 的 `reference_images` 必须按 `reference_roles` 原顺序传给 `image_gen`，完成后保存到 `expected_output`。

- `identity_reference`：只锁定真人身份。
- `content_reference`：锁定当前视频真实的官方品牌物、产品或结果，不继承来源图的文字与布局。
- `style_reference`：只学习构图、层级、字体、材质和配色，绝不复制文字、人脸、事实、UI 或主体。
- 两条路线必须在构图、主视觉、证明方式和配色气质上有明显区别。
- 使用 `camera_review_editorial` 时，保留“超大比较标题 + 前景真人 + 一条胶片样片 + 器材阵列”的传播结构，两版仍要改变主视觉重心和空间关系。
- 使用 `creator_product_interaction` 时，保留“巨大短标题 + 真人态度 + 一个准确品牌物 + 明确互动”的传播结构；从持物、递近、吸附/开启等动作中选择两种，品牌物必须来自当前官方 `content_reference`。

生成后逐张读图。默认直接在 Codex 对话内按路线展示通过质检的原图，不创建、不打开 HTML 评审页。每张完成后立即展示；不要等两张全部结束才第一次反馈。文字或尺寸明显不合格时，只按快交付规则重做该路线，并明确告诉用户正在修正什么。

只有用户明确要求“评审页”“浏览器对比页”“批量汇报页”时，才运行：

```bash
python3 scripts/generate_showcase_review_page.py \
  --manifest "$WORKDIR/covers_3x4/cover_requests.json" \
  --output "$WORKDIR/封面评审页_3x4.html"
```

评审页不得放在默认生成链路或用户等待链路中。用户能在 Codex 内看图时，直接展示原图并让用户回复路线编号。

只交付过质检的图。按原图和 `180x240` 缩略图同时判断：一级钩子、一个主证明物、人物信任是否成立；有错字、叠字、断肢、人物漂移、课程海报/仪表盘感、两版同质化或参考图内容泄漏，就针对问题路线处理，不重做已通过的图。

登记真实成片并等用户选择：

```bash
python3 scripts/cover_workflow_state.py register-candidate \
  --job "$WORKDIR/cover_job.json" --ratio 3:4 --route '<route>' --image '<actual-image>' \
  --manifest "$WORKDIR/covers_3x4/cover_requests.json"
python3 scripts/cover_workflow_state.py select-vertical \
  --job "$WORKDIR/cover_job.json" --route '<selected-route>'
```

### 4. 生成 4:3：只续作选中的 3:4

选中竖版后才允许执行：

```bash
python3 scripts/codex_showcase_prompt_builder.py \
  --job "$WORKDIR/cover_job.json" --analysis "$WORKDIR/analysis.json" \
  --ratio 4:3 --engine image2 --out "$WORKDIR/covers_4x3"
```

该命令默认只产生一张原生横版：`thumbnail`。必须保留选中竖版的标题、人物身份和服装、英雄物、配色氛围、字体材质和传播关系；允许为横版重建标题断行、人物位置、机位、景别和前后景。只有用户明确要求对照时才传 `--landscape-variants both` 生成 `faithful` 和 `thumbnail`；需要仅忠实延续时传 `--landscape-variants faithful`，仍只出一张。严禁使用 `generate_landscape_from_cover.py`、Pillow 拉伸、拼贴或裁切。

以 `320x240` 缩略图检查横版：一级钩子应占视觉面积约 45%-60%，必须比主题标签更大、更可读；人物不能退成远景，人物/英雄物和标题通过穿插、遮挡与透视形成一个整体，而不是左右各放半张图。含“产品名 + 中文结论”的标题必须做两级字块：产品名退为识别锚点，中文结论成为约 1.7-2 倍字高的第一视觉，禁止两行平均用力。对 `creator_product_interaction`，可以把同一品牌物重设为广角递近前景，但不能换 Logo、换人物或缩小标题；若模型无法稳定处理持物接触，品牌物固定在独立底座，人物只做留有明确空隙的单指指向，禁止半接半捧、悬浮在手间或手指穿模。默认单张通过后，登记候选并以 `select-landscape` 设为最终交付，job 完成；只有用户要求多张对照时再等用户选横版。

### 5. Dreamina / Seedream 备选或对照

Image 2 未达标、用户要求 Seedream、或用户要求同题 A/B 时，复用同一 job：

```bash
python3 scripts/codex_showcase_prompt_builder.py \
  --job "$WORKDIR/cover_job.json" --analysis "$WORKDIR/analysis.json" \
  --ratio 3:4 --engine dreamina --dreamina-model auto \
  --dreamina-mode recipe-direct --dreamina-resolution 2k \
  --out "$WORKDIR/covers_seedream"
```

读取 manifest 中的 `dreamina_command`，先核对模型能力、比例、标题契约和路径，再原生执行：

```bash
python3 scripts/execute_dreamina_manifest.py \
  --manifest "$WORKDIR/covers_seedream/cover_requests.json"
```

该脚本不会二次裁切；比例按快交付规则检查，明显不符时失败。不要用旧 `generate_ai_covers.py` 传输 4:3 请求，因为它会按历史竖版画布裁图。不要把两台模型的输出混成“不同创意路线”；它们是同一创意计划的不同渲染器。

Dreamina 必须走自己的适配器，不直接复用 Image 2 长提示词：

- 默认 `recipe-direct` 对齐已验收的 v1.1：真人路线只传一张 `identity_reference`，无人路线纯 `text2image`；不传案例封面、选中竖版、UI 截图或内容帧。模型靠题材配方直生，不做垫图模仿。唯一例外是 `creator_product_interaction`：品牌物精度决定成败时使用 `grounded`，参考图严格限制为一张身份图加一张当前官方品牌资产。
- 默认使用 `2K`。`4K` 只作为固定其他变量后的单独 A/B，不把更高分辨率误当作更好构图。
- Dreamina 的 4:3 仍要求用户先选中 3:4，默认把该成片作为 `selected_vertical_reference`，并结合身份图、官方品牌物和 Dreamina 短配方原生重构横版；它是系列续作参考，不是扩图母版。若参考导致横版机械照搬、重复文字或构图变挤，仅重跑该横版并使用 `--no-dreamina-use-selected-cover` 回退到无成片参考的原生重生。
- 提示词必须是短中文视觉配方：主题、单一构图、一个结果物、人物动作、字体材质、配色和禁项。不要带完整视频分析、证明链、英文续作契约或多套相反构图。
- 从“冲击海报 / 复古编辑 / 电影场景”路线库中默认只选两条，构图和材质都要拉开，不只是换人物姿势；不要求把路线库全部生成。
- `creator_product_interaction` 从“稳定持物 / 广角递近 / 动态拔高”路线库中默认只选两条，都要守住准确文字、人物和品牌物。动态拔高可使用立体编辑大字、官方品牌色侧光、近景品牌物和更强动作。其 4:3 动态版默认采用“品牌物固定落地 + 人物明确指向”，不复用竖版的双手递近或接住动作；标题按产品锚点与结论重字分级。两版不得退化为同一张黑底产品肖像。
- 只有真实主体精度明显比美感更重要时，才显式改用 `--dreamina-mode grounded --content-reference '<结果帧>'`；一次最多再加一张内容图，并单独质检 UI 泄漏和版式变碎。
- 先看 `180x240` 缩略图。大面积空底、画中画、截图矩形、椅子原背景、杂字、人物近脸贴图或服装漂移，均视为失败并只重跑对应路线。

旧 Seedream 保底命令和配方保持独立，不用新适配器覆盖；新旧模型对照时固定视频、文案、人像、内容帧、比例和路线，只改变模型或适配器一个变量。

## 参考资料

- [deepseek_portrait_showcase.md](references/deepseek_portrait_showcase.md)：自然人像、原创主物、原生横竖续作及回选原版的案例。

- [cover_title_strategy.md](references/cover_title_strategy.md)：标题的“锚点 + 理由”。
- [style_profiles.json](references/style_profiles.json)：已验证的视觉风格族和同比例参考图。
- [style_reference_workflow.md](references/style_reference_workflow.md)：参考图角色与内容泄漏防线。
- [creator_product_interaction_playbook.md](references/creator_product_interaction_playbook.md)：真人、官方品牌物与广角互动的竖横版规则。
- [story_hook_black_gold_design_review.md](references/story_hook_black_gold_design_review.md)：从课程海报重置为抖音精选缩略图的方法。
- [claude_code_black_orange_showcase.md](references/claude_code_black_orange_showcase.md)：用户确认的无人像黑橙 showcase；痛点大字、单一场景、去底部角标的设计复盘。
- [douyin_cover_standard.md](references/douyin_cover_standard.md)：平台硬红线。

`cover_pipeline.py`、`run_cover_workflow.py` 和旧 Seedream 文档仅用于历史保底或已有评测。不要让它们覆盖 v2 的状态门、创意计划和横版续作规则。
