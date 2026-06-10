# 封面质量评测闭环（PASS@k Harness）

> 对应 05-28 对齐会老板要求的"评测机制 + 规模化命中率"。这套闭环把"反推打磨 → 自动判合格 → 出 PASS@k 命中率 → 演示看板"工程化。当前以**科技垂类**为样板跑通，可平移到其他垂类。

## 4 个脚本 + 1 份标准

| 文件 | 作用 |
|---|---|
| `references/tech_cover_checklist.md` | 科技垂类的**合格标准**（12 项编号验收表）。喂给 judge，也是交给梦琪规模化测试的判据。 |
| `scripts/judge_cover_quality.py` | 单张封面 VLM judge：7 维打分 + 错字双保险 + PASS 判定。 |
| `scripts/sample_and_pick.py` | 同一 prompt 跑 N 批、每张 judge、自动选最优。 |
| `scripts/eval_passk.py` | 多视频聚合 PASS@1/2/4 命中率。 |
| `scripts/generate_passk_dashboard.py` | 演示看板 HTML。 |

## 端到端命令

```bash
# 环境（同一个 ARK key）
export VCG_VLM_API_KEY=...  VCG_IMAGE_API_KEY=...

# 每个视频：先跑到 prompts（产出 analysis.json + prompts.seedream.text.json）
python3 scripts/run_cover_workflow.py --video <视频> --stop-after prompts

# 每个视频：N 批采样 + judge 选最优（B1 同策略跨批口径）
python3 scripts/sample_and_pick.py --workdir <workdir> \
  --variant balanced --n-batches 4 --vertical tech --pass-threshold 7.0

# 所有视频跑完：聚合 PASS@k + 出看板
python3 scripts/eval_passk.py --workdirs <wd1> <wd2> ... --output passk_summary.json
python3 scripts/generate_passk_dashboard.py --summary passk_summary.json --output dashboard.html
```

## 评分维度与合格判定

judge 输出 7 维分（权重见 `tech_cover_checklist.md` 映射表），`overall = 加权平均`。

**PASS = `overall ≥ 阈值（默认 7.0）` 且 `critical_issues 为空`。**

critical（任一触发即打回，不管分多高）：
- 主/副标题**错字**（VLM 读字 + 程序侧归一化字符串比对双保险）
- 标题**语义不符**（`title_semantic_match < 6`，对照视频 content_summary）
- **排版崩**（`text_layout < 6`：挤压/压主体/断行不可读/贴边）
- 生成视频里不存在的**假人脸**

## PASS@k 口径（重要）

- 定义：`pass_i@k = 前 k 张候选里至少 1 张合格`（按**生成顺序**，不按分数排序，否则灌水）。
- 整体 `PASS@k = M 个视频的平均命中率`，数学上 PASS@1 ≤ PASS@2 ≤ PASS@4。
- 采样粒度默认 **B1：固定一个 variant 跨批**（`--variant balanced`），与"竞品一视频一图"口径公平可比。
- ⚠️ 若改成跨 variant 混池（B2），PASS@k 会偏乐观，跟竞品对比口径要先说清。

## 校准结论（judge 已验证可信）

用历史图校准（`workspace/iteration-2.5` 错字图、`iteration-3` 正确图、结构力学 batch 采样）：
- ✅ 正确图不误报（子串豁免，避免把 kicker/标签连读当错字）
- ✅ 真错字精准打回：「桁架」→「析架」(dist=1)、「桁架」→「柩架」均被抓 critical，且整体分高（8.0）也照样打回
- ✅ 垂类错配可发现：cyberpunk K 线图用在土木内容上被 judge 标为 issue

## 交接给梦琪 / magicx 的接口

`judge_cover_quality.py` 的 `call_vlm()` 是唯一网络出口（纯 HTTP + `VCG_VLM_*` 环境变量）。
接 magicx 只需替换环境变量或在 `call_vlm` 加一个 provider 分支，其余逻辑不动。
`tech_cover_checklist.md` + judge 的评分 prompt 就是规模化测试的"合格标准"。

## 平移到新垂类

1. 写 `references/<vertical>_cover_checklist.md`（仿 tech 的 12 项表）
2. judge 调用时传 `--vertical <vertical>`（自动加载对应 checklist）
3. sample/passk/dashboard 脚本**零改动**复用
