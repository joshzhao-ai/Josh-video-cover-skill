#!/usr/bin/env python3
"""
PASS@k 聚合。

读 M 个视频的 eval/candidates.json，按**生成顺序**（非分数排序）算每个视频的
pass@k = 前 k 张候选里至少 1 张合格，整体 PASS@k = M 个视频的平均命中率。

PASS@k 的产品含义：跟竞品比，掷 k 次骰子，用户能不能拿到一张能交付的图。
必须用生成顺序（不能事后挑分数最高的前 k 张，否则灌水成恒等于 PASS@N）。
数学上 PASS@1 ≤ PASS@2 ≤ PASS@4（单调不减）。
"""
import argparse
import json
from pathlib import Path


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def pass_at_k(flags, k):
    """前 k 张里至少 1 张合格。候选数 < k 时用全部候选。"""
    window = flags[:k]
    return 1 if any(window) else 0


def main():
    parser = argparse.ArgumentParser(description="Aggregate PASS@k across videos from candidates.json files.")
    parser.add_argument("--candidates", nargs="+", help="candidates.json 路径列表。")
    parser.add_argument("--workdirs", nargs="+", help="workdir 列表，取 <wd>/eval/candidates.json。")
    parser.add_argument("--ks", default="1,2,4", help="逗号分隔的 k 值，默认 1,2,4。")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    paths = []
    if args.candidates:
        paths += [Path(p).expanduser() for p in args.candidates]
    if args.workdirs:
        paths += [Path(w).expanduser() / "eval" / "candidates.json" for w in args.workdirs]
    if not paths:
        raise SystemExit("需要 --candidates 或 --workdirs。")

    ks = [int(x) for x in args.ks.split(",")]
    per_video = []
    for path in paths:
        if not path.exists():
            print(f"[warn] 跳过缺失：{path}")
            continue
        data = load_json(path)
        flags = [1 if c.get("passed") else 0 for c in data.get("candidates", [])]
        row = {
            "workdir": data.get("workdir"),
            "title": data.get("title"),
            "subtitle": data.get("subtitle"),
            "vertical": data.get("vertical"),
            "variant": data.get("variant"),
            "n_candidates": len(flags),
            "passed_flags": flags,
            "first_pass_rank": data.get("first_pass_rank"),
            "best_score": (data.get("best") or {}).get("overall_score"),
            "candidates_path": str(path),
        }
        for k in ks:
            row[f"pass@{k}"] = pass_at_k(flags, k)
        per_video.append(row)

    num = len(per_video)
    pass_at = {}
    for k in ks:
        pass_at[str(k)] = round(sum(r[f"pass@{k}"] for r in per_video) / num, 4) if num else 0.0

    summary = {
        "num_videos": num,
        "ks": ks,
        "pass_at_k": pass_at,
        "per_video": per_video,
    }
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"num_videos": num, "pass_at_k": pass_at}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
