#!/usr/bin/env python3
"""
批量采样 + 自动选最优。

对同一组 prompt 跑 N 批（默认固定一个 variant，即 PASS@k 的"同策略跨批"口径 B1），
每张过 judge_cover_quality.py 打分，按 overall_score 选 best，产出 eval/candidates.json。

幂等：batch 图 / judge JSON 已存在则跳过，支持断点续跑（避免大批量跑到一半挂掉前功尽弃）。

依赖（subprocess 调用，零改动复用）：
- generate_ai_covers.py：每批一个 --output-dir，出图
- judge_cover_quality.py：每张封面 VLM 打分
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def make_variant_prompts(prompts, variant, dst):
    """裁剪出只含目标 variant 的 prompts，喂给 generate_ai_covers（每批只出 1 张，省成本）。"""
    variants = [v for v in prompts.get("variants", []) if v.get("name") == variant]
    if not variants:
        available = [v.get("name") for v in prompts.get("variants", [])]
        raise SystemExit(f"variant '{variant}' 不在 prompts 中；可选：{available}")
    sub = dict(prompts)
    sub["variants"] = variants
    Path(dst).write_text(json.dumps(sub, ensure_ascii=False, indent=2), encoding="utf-8")


def run_batch(variant_prompts, batch_dir):
    batch_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "generate_ai_covers.py"),
         "--prompts", str(variant_prompts), "--output-dir", str(batch_dir)],
        check=True,
    )


def judge_one(cover, analysis, title, subtitle, vertical, threshold, out_json):
    subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "judge_cover_quality.py"),
         "--cover", str(cover), "--analysis", str(analysis),
         "--title", title, "--subtitle", subtitle, "--vertical", vertical,
         "--pass-threshold", str(threshold), "--output", str(out_json)],
        check=True, stdout=subprocess.DEVNULL,
    )
    return load_json(out_json)


def main():
    parser = argparse.ArgumentParser(description="Sample N batches of one variant, judge each, pick the best.")
    parser.add_argument("--workdir", required=True, help="含 prompts + analysis.json 的工作目录。")
    parser.add_argument("--prompts", help="默认 <workdir>/prompts.seedream.text.json")
    parser.add_argument("--analysis", help="默认 <workdir>/analysis.json")
    parser.add_argument("--title", help="期望主标题，默认从 prompts 读。")
    parser.add_argument("--subtitle", help="期望副标题，默认从 prompts 读。")
    parser.add_argument("--vertical", default="tech")
    parser.add_argument("--variant", default="balanced", help="固定采样的 variant（PASS@k B1 同策略跨批）。")
    parser.add_argument("--n-batches", type=int, default=4)
    parser.add_argument("--pass-threshold", type=float, default=7.0)
    args = parser.parse_args()

    workdir = Path(args.workdir).expanduser().resolve()
    prompts_path = Path(args.prompts).expanduser() if args.prompts else workdir / "prompts.seedream.text.json"
    analysis_path = Path(args.analysis).expanduser() if args.analysis else workdir / "analysis.json"
    if not prompts_path.exists():
        raise SystemExit(f"prompts 不存在：{prompts_path}（先跑 run_cover_workflow.py --stop-after prompts）")
    prompts = load_json(prompts_path)
    title = args.title or prompts.get("title", "")
    subtitle = args.subtitle if args.subtitle is not None else prompts.get("subtitle", "")

    eval_dir = workdir / "eval"
    judge_dir = eval_dir / "judge"
    judge_dir.mkdir(parents=True, exist_ok=True)
    variant_prompts = eval_dir / f"prompts_{args.variant}.json"
    make_variant_prompts(prompts, args.variant, variant_prompts)

    candidates = []
    for b in range(1, args.n_batches + 1):
        batch_dir = eval_dir / f"batch_{b:02d}"
        cover = batch_dir / f"{args.variant}.jpg"
        if not cover.exists():  # 幂等：已出图则跳过
            run_batch(variant_prompts, batch_dir)
        if not cover.exists():
            print(f"[warn] batch {b} 出图失败，跳过", file=sys.stderr)
            continue
        judge_json = judge_dir / f"batch_{b:02d}_{args.variant}.json"
        jd = load_json(judge_json) if judge_json.exists() else judge_one(
            cover, analysis_path, title, subtitle, args.vertical, args.pass_threshold, judge_json)
        candidates.append({
            "batch": b,
            "variant": args.variant,
            "image": str(cover.relative_to(workdir)),
            "judge": str(judge_json.relative_to(workdir)),
            "overall_score": jd["overall_score"],
            "passed": jd["passed"],
            "detected_title": jd.get("detected_title", ""),
            "detected_subtitle": jd.get("detected_subtitle", ""),
            "critical_issues": jd.get("critical_issues", []),
        })

    best = max(candidates, key=lambda c: c["overall_score"]) if candidates else None
    # first_pass_rank 按生成顺序（candidates 已按 batch 顺序），用于 PASS@k
    first_pass_rank = next((c["batch"] for c in candidates if c["passed"]), None)
    if best:
        shutil.copy(workdir / best["image"], eval_dir / "best.jpg")

    manifest = {
        "workdir": str(workdir),
        "vertical": args.vertical,
        "title": title,
        "subtitle": subtitle,
        "n_batches": args.n_batches,
        "variant": args.variant,
        "pass_threshold": args.pass_threshold,
        "candidates": candidates,
        "best": ({"batch": best["batch"], "image": best["image"], "overall_score": best["overall_score"]} if best else None),
        "video_passed": first_pass_rank is not None,
        "first_pass_rank": first_pass_rank,
    }
    out = eval_dir / "candidates.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    n_pass = sum(1 for c in candidates if c["passed"])
    print(f"[done] {len(candidates)} 候选，{n_pass} 张合格，best overall="
          f"{best['overall_score'] if best else 'NA'}，first_pass_rank={first_pass_rank}")
    print(f"[out] {out}")


if __name__ == "__main__":
    main()
