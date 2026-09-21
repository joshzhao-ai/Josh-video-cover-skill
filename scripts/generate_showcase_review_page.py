#!/usr/bin/env python3
"""Generate a review board that shows both full-size and feed-size covers."""

import argparse
import html
import json
from pathlib import Path


def rel(path, base):
    return Path(path).resolve().relative_to(base.resolve()).as_posix()


def read_json(path):
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def route_card(item, output):
    image_path = Path(item.get("expected_output", ""))
    ratio = item.get("ratio", "3:4")
    aspect = "3 / 4" if ratio == "3:4" else "4 / 3"
    thumb_width = "180px" if ratio == "3:4" else "320px"
    if image_path.exists():
        source = html.escape(rel(image_path, output.parent))
        media = f'<img class="full" src="{source}" alt="{html.escape(item.get("name", "cover"))}">'
        thumb = f'<img class="thumb" src="{source}" alt="{html.escape(item.get("name", "cover"))} thumbnail">'
    else:
        media = '<div class="placeholder">Missing image</div>'
        thumb = '<div class="thumb placeholder">Missing image</div>'
    route = item.get("creative_route", {})
    copy = item.get("copy", {})
    source_cover = item.get("source_cover", "")
    continuation = "Selected 3:4 continuation" if source_cover else "New 3:4 direction"
    return f"""
      <article style="--aspect:{aspect}; --thumb-width:{thumb_width}">
        <div class="media">{media}</div>
        <div class="info">
          <div class="eyebrow">{html.escape(ratio)} · {html.escape(continuation)}</div>
          <h2>{html.escape(item.get('route_label', item.get('name', '')))}</h2>
          <p class="route">{html.escape(item.get('name', ''))}</p>
          <p><strong>一级钩子</strong>：{html.escape(copy.get('primary', ''))}</p>
          <p><strong>主题标签</strong>：{html.escape(copy.get('topic_label', ''))}</p>
          <p><strong>画面路径</strong>：{html.escape(route.get('territory', ''))}</p>
          <p><strong>证明物</strong>：{html.escape(item.get('hero_object', ''))} + {html.escape(item.get('evidence_object', ''))}</p>
        </div>
        <div class="thumb-wrap">
          <span>信息流缩略预览</span>
          {thumb}
        </div>
      </article>"""


def main():
    parser = argparse.ArgumentParser(description="Generate a review page for v2 cover requests.")
    parser.add_argument("--manifest", required=True, help="cover_requests.json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    manifest_path = Path(args.manifest).expanduser().resolve()
    manifest = read_json(manifest_path)
    output = Path(args.output).expanduser().resolve()
    routes = manifest.get("routes", [])
    plan = manifest.get("creative_plan", {})
    copy = plan.get("copy", {})
    title = " / ".join(item for item in [copy.get("title", ""), copy.get("hook", "")] if item) or "Cover Review"
    cards = "".join(route_card(item, output) for item in routes)
    checks = "".join(f"<li>{html.escape(str(item))}</li>" for item in manifest.get("review_contract", {}).get("must_check", []))
    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} · Cover Review</title>
  <style>
    :root {{ color-scheme:dark; --bg:#0b0c0f; --panel:#16191f; --line:#303640; --text:#f5f7fa; --muted:#a3adba; --accent:#f2b84b; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--text); background:var(--bg); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    header {{ padding:32px clamp(18px,5vw,64px) 22px; border-bottom:1px solid var(--line); }}
    h1 {{ margin:0 0 8px; font-size:clamp(28px,5vw,48px); }}
    .meta, li {{ color:var(--muted); line-height:1.55; }}
    .checks {{ margin:18px 0 0; padding-left:20px; max-width:980px; display:grid; gap:4px; }}
    .grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:20px; padding:28px clamp(18px,5vw,64px) 48px; align-items:start; }}
    article {{ background:var(--panel); border:1px solid var(--line); border-radius:14px; overflow:hidden; box-shadow:0 16px 40px rgba(0,0,0,.2); }}
    .media {{ background:#232832; }}
    .full, .placeholder {{ display:block; width:100%; aspect-ratio:var(--aspect); object-fit:cover; }}
    .placeholder {{ display:grid; place-items:center; min-height:260px; color:var(--muted); }}
    .info {{ padding:16px 16px 8px; }}
    .eyebrow {{ color:var(--accent); font-size:12px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }}
    h2 {{ margin:8px 0 4px; font-size:21px; }}
    p {{ margin:7px 0; color:var(--muted); line-height:1.45; }}
    strong {{ color:var(--text); }}
    .route {{ color:var(--accent); font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; }}
    .thumb-wrap {{ padding:12px 16px 18px; border-top:1px solid var(--line); }}
    .thumb-wrap span {{ display:block; margin-bottom:8px; color:var(--muted); font-size:12px; }}
    .thumb {{ display:block; width:min(100%,var(--thumb-width)); aspect-ratio:var(--aspect); object-fit:cover; border:1px solid #48515e; border-radius:4px; }}
    @media (max-width:980px) {{ .grid {{ grid-template-columns:1fr; max-width:600px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(title)}</h1>
    <div class="meta">同一创意计划下的路线级候选。请先按缩略图判断一级钩子，再看证明物、人物和风格是否成立。</div>
    <ul class="checks">{checks}</ul>
  </header>
  <main class="grid">{cards}</main>
</body>
</html>
"""
    output.write_text(page, encoding="utf-8")


if __name__ == "__main__":
    main()
