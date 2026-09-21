---
name: video-cover-generator
description: "为抖音、快手、小红书和视频号短视频生成高点击封面。输入本地视频时，按强制流程完成视频分析、真人人像选择、标题候选确认、三张差异化 3:4 封面、选中竖版的原生 4:3 横版和缩略图质检。用户提到封面、封面图、视频封面、抖音封面、短视频封面、给视频配图、做个封面或生成封面时必须使用。"
---

# Video Cover Generator v2.0

目标不是“按提示词出三张图”，而是交付一张在信息流缩略图里仍然有美感、表达清晰、值得点击的封面。

## 设计原则

- **一个内容决策，两套模型适配器。** 两个引擎共享用户确认的文案、人物选择、英雄物和风格方向，但各自使用已经验证的提示词结构；禁止把 Image 2 的长契约直接翻译给 Dreamina。
- **用户决策先于生图。** 真人视频必须先选人像策略；除非用户明确说“全自动”，必须先给标题候选并等用户确认。没有确认标题，不得生成最终封面。
- **横版是同一 campaign 的原生续作。** Image 2 和 Dreamina 默认都读取选中的 3:4 成片作为 `selected_vertical_reference`，继承文案、人物、英雄物、配色、字体材质和传播关系，但允许为横版重新设计机位、断行、景别与前后景。Dreamina 同时保留自己的短中文视觉配方；两者都生成原生 4:3，不裁切、拉伸或拼贴。
- **封面只传达一件事。** 一级钩子、一个大结果/证明物、一个真人或辅助证据就够了。UI、代码、网格和粒子只能做低对比氛围。
- **强结果可追溯。** 数字、收入、涨粉、权威、排名或“靠 X 达到 Y”只能来自视频、字幕、标题、用户补充或 `verified_proof`。

## 引擎策略

| 用途 | 引擎 | 规则 |
| --- | --- | --- |
| 默认主推 | Codex `image_gen` / GPT Image 2 | 使用风格参考、人物身份参考和严格的画面契约，先争取视觉上限。 |
| 稳定备选 | Dreamina / Seedream | 默认 `5.0 + 2K + recipe-direct`；共享内容决策，但使用 Dreamina 题材短配方。只在用户要求或双引擎对照时使用。 |
| 历史保底 | `scripts/cover_pipeline.py --engine dreamina` | 保留旧链路与旧 Seedream 配方，不把 Image 2 的提示词反灌进去。 |

不要猜 Seedream 版本。先运行：

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

先读 [cover_title_strategy.md](references/cover_title_strategy.md) 并准备 3 个标题候选。`has_real_person=true` 时，在同一条消息里同时展示两组选项：

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

即使封面主体更像硬币、产品、实物或流程，只要视频有清晰真人仍要展示人像选项。用户一次回复后，依次记录两项状态：

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

标题阶段只展示一套完整候选，不额外让用户选择“创意短写”。当视频命中创意拔高路线时，A/B 使用用户确认的完整文案；C 可以自动压缩为保留锚点的短判断，但不能新增事实、数字或更强结论。展示成片时必须明确说明 C 使用了什么短写，让用户通过选图决定是否接受。用户要求文案一个字不改时禁止自动压缩。

### 3. 生成 3:4：三条视觉路线，不是同一张图换姿势

默认生成 Image 2 请求：

```bash
python3 scripts/codex_showcase_prompt_builder.py \
  --job "$WORKDIR/cover_job.json" --analysis "$WORKDIR/analysis.json" \
  --ratio 3:4 --engine image2 --out "$WORKDIR/covers_3x4"
```

读取 `$WORKDIR/covers_3x4/cover_requests.json`。每个 route 的 `reference_images` 必须按 `reference_roles` 原顺序传给 `image_gen`，完成后保存到 `expected_output`。

- `identity_reference`：只锁定真人身份。
- `content_reference`：锁定当前视频真实的官方品牌物、产品或结果，不继承来源图的文字与布局。
- `style_reference`：只学习构图、层级、字体、材质和配色，绝不复制文字、人脸、事实、UI 或主体。
- 三路线必须在构图、主视觉、证明方式和配色气质上不同。
- 使用 `camera_review_editorial` 时，保留“超大比较标题 + 前景真人 + 一条胶片样片 + 器材阵列”的传播结构，但三路线仍要改变主视觉重心和空间关系，不能复制同一版式三次。
- 使用 `creator_product_interaction` 时，保留“巨大短标题 + 真人态度 + 一个准确品牌物 + 明确互动”的传播结构；三路线至少分别测试持物、递近、吸附/开启等不同动作，品牌物必须来自当前官方 `content_reference`。

生成后逐张读图。默认直接在 Codex 对话内按路线展示通过质检的原图，不创建、不打开 HTML 评审页。每张完成后立即展示；不要等三张全部结束才第一次反馈。尺寸或文字失败时只重做该路线，并明确告诉用户正在修正什么。

只有用户明确要求“评审页”“浏览器对比页”“批量汇报页”时，才运行：

```bash
python3 scripts/generate_showcase_review_page.py \
  --manifest "$WORKDIR/covers_3x4/cover_requests.json" \
  --output "$WORKDIR/封面评审页_3x4.html"
```

评审页不得放在默认生成链路或用户等待链路中。用户能在 Codex 内看图时，直接展示原图并让用户回复路线编号。

只交付过质检的图。按原图和 `180x240` 缩略图同时判断：一级钩子、一个主证明物、人物信任是否成立；有错字、叠字、断肢、人物漂移、课程海报/仪表盘感、三张同质化或参考图内容泄漏，就针对该路线重做。

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

该命令会产生两张原生横版候选：`faithful` 和 `thumbnail`。两者都必须保留选中竖版的标题、人物身份和服装、英雄物、配色氛围、字体材质和传播关系；允许为横版重建标题断行、人物位置、机位、景别和前后景。严禁使用 `generate_landscape_from_cover.py`、Pillow 拉伸、拼贴或裁切。

以 `320x240` 缩略图检查横版：一级钩子应占视觉面积约 45%-60%，必须比主题标签更大、更可读；人物不能退成远景，人物/英雄物和标题通过穿插、遮挡与透视形成一个整体，而不是左右各放半张图。含“产品名 + 中文结论”的标题必须做两级字块：产品名退为识别锚点，中文结论成为约 1.7-2 倍字高的第一视觉，禁止两行平均用力。对 `creator_product_interaction`，可以把同一品牌物重设为广角递近前景，但不能换 Logo、换人物或缩小标题；若模型无法稳定处理持物接触，品牌物固定在独立底座，人物只做留有明确空隙的单指指向，禁止半接半捧、悬浮在手间或手指穿模。登记候选、选择最终横版后 job 才完成。

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

该脚本不会二次裁切；Dreamina 返回的尺寸与 manifest 比例不符时直接失败。不要用旧 `generate_ai_covers.py` 传输 4:3 请求，因为它会按历史竖版画布裁图。不要把两台模型的输出混成“不同创意路线”；它们是同一创意计划的不同渲染器。

Dreamina 必须走自己的适配器，不直接复用 Image 2 长提示词：

- 默认 `recipe-direct` 对齐已验收的 v1.1：真人路线只传一张 `identity_reference`，无人路线纯 `text2image`；不传案例封面、选中竖版、UI 截图或内容帧。模型靠题材配方直生，不做垫图模仿。唯一例外是 `creator_product_interaction`：品牌物精度决定成败时使用 `grounded`，参考图严格限制为一张身份图加一张当前官方品牌资产。
- 默认使用 `2K`。`4K` 只作为固定其他变量后的单独 A/B，不把更高分辨率误当作更好构图。
- Dreamina 的 4:3 仍要求用户先选中 3:4，默认把该成片作为 `selected_vertical_reference`，并结合身份图、官方品牌物和 Dreamina 短配方原生重构横版；它是系列续作参考，不是扩图母版。若参考导致横版机械照搬、重复文字或构图变挤，仅重跑该横版并使用 `--no-dreamina-use-selected-cover` 回退到无成片参考的原生重生。
- 提示词必须是短中文视觉配方：主题、单一构图、一个结果物、人物动作、字体材质、配色和禁项。不要带完整视频分析、证明链、英文续作契约或多套相反构图。
- 三路线分别使用“冲击海报 / 复古编辑 / 电影场景”视觉语法，构图和材质都要拉开，不只是换人物姿势。
- `creator_product_interaction` 使用“稳定持物 / 广角递近 / 动态拔高”三路线。前两版守住准确文字、人物和品牌物；第三版使用立体编辑大字、官方品牌色侧光、近景品牌物和更强动作争取 Showcase 上限。其 4:3 动态版默认采用“品牌物固定落地 + 人物明确指向”，不复用竖版的双手递近或接住动作；标题按产品锚点与结论重字分级。三版不得退化为同一张黑底产品肖像。
- 只有真实主体精度明显比美感更重要时，才显式改用 `--dreamina-mode grounded --content-reference '<结果帧>'`；一次最多再加一张内容图，并单独质检 UI 泄漏和版式变碎。
- 先看 `180x240` 缩略图。大面积空底、画中画、截图矩形、椅子原背景、杂字、人物近脸贴图或服装漂移，均视为失败并只重跑对应路线。

旧 Seedream 保底命令和配方保持独立，不用新适配器覆盖；新旧模型对照时固定视频、文案、人像、内容帧、比例和路线，只改变模型或适配器一个变量。

## 参考资料

- [cover_title_strategy.md](references/cover_title_strategy.md)：标题的“锚点 + 理由”。
- [style_profiles.json](references/style_profiles.json)：已验证的视觉风格族和同比例参考图。
- [style_reference_workflow.md](references/style_reference_workflow.md)：参考图角色与内容泄漏防线。
- [creator_product_interaction_playbook.md](references/creator_product_interaction_playbook.md)：真人、官方品牌物与广角互动的竖横版规则。
- [story_hook_black_gold_design_review.md](references/story_hook_black_gold_design_review.md)：从课程海报重置为抖音精选缩略图的方法。
- [douyin_cover_standard.md](references/douyin_cover_standard.md)：平台硬红线。

`cover_pipeline.py`、`run_cover_workflow.py` 和旧 Seedream 文档仅用于历史保底或已有评测。不要让它们覆盖 v2 的状态门、创意计划和横版续作规则。
