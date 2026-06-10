# End-to-End Pipeline Validation 2026-05-19

## 新增主流程

主入口：

```bash
python3 scripts/run_cover_workflow.py --video '<video.mp4>'
```

全自动验证入口：

```bash
python3 scripts/run_cover_workflow.py \
  --video '<video.mp4>' \
  --auto \
  --cover-variant balanced \
  --landscape-retries 1
```

核心产物：

- `workflow_state.json`
- `workflow_report.json`
- `workflow_report.md`
- `review.seedream.text.html`
- `quality.seedream.text.json`
- `consistency.cross-format.json`

主流程支持：

- 抽帧
- VLM 分析
- 真人身份门控
- 标题选择
- 3:4 三封面生成
- 3:4 选择
- 4:3 横版生成
- 横竖版一致性检查
- 一致性失败后重跑 4:3
- API 失败时写入 failed 状态，方便续跑

## OpenClaw 验证

验证视频：

- `/Users/bytedance/Desktop/Open Claw为什么爆火？ (1).mp4`

最终通过工作目录：

- `/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260518_201532`

关键文件：

- `workflow_report.md`
- `workflow_state.json`
- `review.seedream.text.html`
- `covers-seedream-text/balanced.jpg`
- `landscape-4x3/landscape.jpg`
- `consistency.cross-format.json`

结果：

- `workflow_state.json`: `completed`
- 3:4 质量检查：通过
- 4:3 横版：复用已通过的 v5 横版
- 横竖版一致性：通过
- 一致性总分：`9.0`

一致性细分：

```json
{
  "title_consistency": 10,
  "subtitle_consistency": 10,
  "subject_consistency": 9.0,
  "style_consistency": 9.0,
  "landscape_composition": 9.0,
  "thumbnail_legibility": 10
}
```

说明：

- 新主流程可在已有 4:3 产物时续跑质检和报告。
- 当横版主体不一致时，一致性检查能抓到问题。
- v5 已把主体修回“C 形红色机械爪 + 蓝色能量球”。

## OpenClaw 新跑尝试

新工作目录：

- `/Users/bytedance/Desktop/video-covers/Open Claw为什么爆火？ (1)_20260519_165523`

结果：

- 抽帧、分析、真人门控、标题选择、3:4 生成、review、质量检查均完成。
- 4:3 生图阶段失败。
- 失败原因：图片接口连续返回 `429 Too Many Requests`。

状态：

- `workflow_state.json`: `failed`
- `workflow_report.md`: 已写入

说明：

- 这是外部图像接口限流，不是主流程逻辑错误。
- 已给 `generate_ai_covers.py` 和 `generate_landscape_from_cover.py` 增加 retry。
- 429 持续出现时，流程会写入 failed 状态，后续可用同一个 `--workdir` 续跑。

## 真人视频验证

验证视频：

- `/Users/bytedance/Downloads/抖音2026518-001588.mp4`

工作目录：

- `/Users/bytedance/Desktop/video-covers/抖音2026518-001588_20260519_170343`

### 门控验证

结果：

- `person_asset_gate.json`: `requires_decision=true`
- 推荐生产选项：
  - `uploaded-photo`
  - `no-person`
- 实验选项：
  - `video-frame`

脚本在没有用户选择时退出：

- exit code: `2`
- `workflow_state.json`: `needs_user_choice`

这符合预期：真人强相关视频不会默认生成 AI 假人像。

### no-person 路径验证

继续使用：

```bash
--person-mode no-person
```

结果：

- 标题选择完成。
- `prompts.seedream.text.json` 生成完成。
- prompt 明确禁止真人、人脸、半身像。
- 3:4 生图阶段失败。

失败原因：

- 图片接口连续返回 `429 Too Many Requests`。

状态：

- `workflow_state.json`: `failed`
- `workflow_report.md`: 已写入

说明：

- no-person 的流程逻辑已验证到 prompt 阶段。
- 图片产出被外部限流挡住，接口恢复后可用同一个 `--workdir` 续跑。

## 本轮代码验证

通过：

```bash
python3 -m py_compile \
  scripts/run_cover_workflow.py \
  scripts/generate_ai_covers.py \
  scripts/generate_landscape_from_cover.py \
  scripts/build_cover_prompts.py \
  scripts/check_cross_format_consistency.py

python3 -m json.tool evals/evals.json
```

## 结论

主流程已经从“多脚本手动拼接”升级为“可运行、可暂停、可续跑、可报告”的 pipeline。

当前唯一没有完全验证的新链路是：真人 no-person 从 prompt 到最终图片产出。这一步被图片 API 429 限流挡住，不是流程逻辑失败。

下一步建议：

1. 等图片接口恢复后，直接续跑真人 no-person 工作目录。
2. 给 `run_cover_workflow.py` 增加一个 `--resume` 说明或命令别名。
3. 后续再做 VLM 二次标题质检，检查错字、裁切和点击力。
