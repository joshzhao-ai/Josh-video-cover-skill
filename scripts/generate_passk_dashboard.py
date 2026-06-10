#!/usr/bin/env python3
"""
PASS@k 演示看板。

读 eval_passk.py 产出的 passk_summary.json，生成暗色看板 HTML：
- 顶部 PASS@1/2/4 超大数字卡（老板第一眼看的）
- 每视频一行：候选图矩阵 + 每张分数 badge + 命中✓/✗ + critical tooltip + best 金边 + 行尾命中灯

图片用绝对路径，本机直接 open 可看（现场演示）。
"""
import argparse
import html
import json
from pathlib import Path

STYLE = """
:root{--bg:#0a0c14;--panel:#12151f;--ink:#e6e9f2;--muted:#9aa3b8;--good:#4ade80;--bad:#f87171;--ok:#fbbf24;--gold:#ffd640;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 -apple-system,BlinkMacSystemFont,"PingFang SC","Segoe UI",sans-serif}
.shell{max-width:1500px;margin:0 auto;padding:28px 22px 70px}
h1{font-size:24px;margin:0 0 4px}
.meta{color:var(--muted);font-size:13px;margin-bottom:22px}
.passk-cards{display:flex;gap:16px;margin:18px 0 26px}
.passk-card{background:var(--panel);border:1px solid #1d2333;border-radius:14px;padding:18px 34px;text-align:center}
.passk-card .k{color:var(--muted);font-size:13px;letter-spacing:1px}
.passk-card .pct{font-size:48px;font-weight:800;color:var(--gold);line-height:1.15}
.vrow{display:flex;gap:16px;background:var(--panel);border:1px solid #1d2333;border-radius:12px;padding:12px;margin-bottom:12px;align-items:center}
.vinfo{width:190px;flex-shrink:0}
.vtitle{font-weight:700;font-size:15px}
.vsub{color:var(--muted);font-size:12px;margin:3px 0 9px}
.lamps .lamp{display:inline-block;padding:2px 8px;border-radius:5px;font-size:11px;margin-right:4px;font-weight:700}
.lamp.on{background:#16321f;color:var(--good)}
.lamp.off{background:#2a1818;color:var(--bad)}
.cands{display:flex;gap:10px;flex-wrap:wrap}
.cand{position:relative;width:120px;aspect-ratio:3/4;border-radius:8px;overflow:hidden;border:2px solid transparent;background:#0e1119}
.cand.best{border-color:var(--gold)}
.cand img{width:100%;height:100%;object-fit:cover;display:block}
.badge{position:absolute;left:4px;top:4px;padding:1px 6px;border-radius:5px;font-size:12px;font-weight:700;background:rgba(0,0,0,.65)}
.badge.good{color:var(--good)} .badge.ok{color:var(--ok)} .badge.bad{color:var(--bad)} .badge.na{color:var(--muted)}
.mark{position:absolute;right:4px;top:4px;width:20px;height:20px;border-radius:50%;text-align:center;line-height:20px;font-weight:800;font-size:13px}
.mark.pass{background:var(--good);color:#04210f}
.mark.fail{background:var(--bad);color:#2a0606}
"""


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def badge_class(score):
    if score is None:
        return "na"
    if score >= 8:
        return "good"
    if score >= 7:
        return "ok"
    return "bad"


def main():
    parser = argparse.ArgumentParser(description="Generate PASS@k demo dashboard HTML.")
    parser.add_argument("--summary", required=True, help="passk_summary.json from eval_passk.py")
    parser.add_argument("--output", required=True)
    parser.add_argument("--title", default="科技垂类封面 PASS@k 看板")
    args = parser.parse_args()

    summary = load_json(args.summary)
    ks = summary["ks"]
    pass_at = summary["pass_at_k"]
    videos = summary["per_video"]

    cards = "".join(
        f'<div class="passk-card"><div class="k">PASS@{k}</div>'
        f'<div class="pct">{round(pass_at[str(k)] * 100)}%</div></div>'
        for k in ks
    )
    variant = videos[0]["variant"] if videos else "-"
    vertical = videos[0]["vertical"] if videos else "-"
    meta = (f'{summary["num_videos"]} 视频 · 垂类 {vertical} · {variant} 策略 · '
            f'PASS 线 overall≥7 且无 critical issue（错字/语义错/排版崩/假人 直接打回）')

    rows = []
    for v in videos:
        manifest = load_json(v["candidates_path"])
        cand = manifest.get("candidates", [])
        workdir = Path(manifest["workdir"])
        best_score = max((c["overall_score"] for c in cand), default=None)
        cells = []
        for c in cand:
            img = (workdir / c["image"]).as_posix()
            score = c["overall_score"]
            mark_pass = c["passed"]
            crit = c.get("critical_issues") or []
            tip = f' title="{html.escape(" / ".join(crit))}"' if crit else ""
            best_cls = " best" if (best_score is not None and score == best_score) else ""
            cells.append(
                f'<div class="cand{best_cls}"{tip}>'
                f'<img src="file://{img}" loading="lazy">'
                f'<div class="badge {badge_class(score)}">{score}</div>'
                f'<div class="mark {"pass" if mark_pass else "fail"}">{"✓" if mark_pass else "✗"}</div>'
                f'</div>'
            )
        lamps = "".join(
            f'<span class="lamp {"on" if v.get(f"pass@{k}") else "off"}">@{k}</span>' for k in ks
        )
        rows.append(
            f'<div class="vrow"><div class="vinfo">'
            f'<div class="vtitle">{html.escape(v.get("title") or "")}</div>'
            f'<div class="vsub">{html.escape(v.get("subtitle") or "")}</div>'
            f'<div class="lamps">{lamps}</div></div>'
            f'<div class="cands">{"".join(cells)}</div></div>'
        )

    doc = (
        f'<!doctype html><html lang="zh"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{html.escape(args.title)}</title><style>{STYLE}</style></head><body><div class="shell">'
        f'<h1>{html.escape(args.title)}</h1><div class="meta">{html.escape(meta)}</div>'
        f'<div class="passk-cards">{cards}</div>{"".join(rows)}</div></body></html>'
    )
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(doc, encoding="utf-8")
    print(f"[out] {output}")


if __name__ == "__main__":
    main()
