#!/usr/bin/env python3
import argparse
import html
import json
from pathlib import Path


def read_json(path, fallback):
    path = Path(path)
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path, base):
    return Path(path).resolve().relative_to(base.resolve()).as_posix()


def main():
    parser = argparse.ArgumentParser(description="Generate an HTML review page for cover variants.")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--covers-dir", help="Cover directory. Defaults to <workdir>/covers.")
    parser.add_argument("--quality", help="Quality JSON path. Defaults to <workdir>/quality.json.")
    args = parser.parse_args()

    workdir = Path(args.workdir).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    covers_dir = Path(args.covers_dir).expanduser().resolve() if args.covers_dir else workdir / "covers"
    analysis = read_json(workdir / "analysis.json", {})
    titles = read_json(workdir / "titles.json", {})
    quality = read_json(args.quality or workdir / "quality.json", {})
    selected_title_path = workdir / "selected_title.txt"
    selected_title = selected_title_path.read_text(encoding="utf-8").strip() if selected_title_path.exists() else ""

    variants = [
        ("info-heavy", "信息优先"),
        ("visual-heavy", "画面优先"),
        ("balanced", "稳妥平衡"),
    ]
    cards = []
    for filename, label in variants:
        image_path = covers_dir / f"{filename}.jpg"
        if image_path.exists():
            cards.append(f"""
      <article class="card">
        <img src="{html.escape(rel(image_path, output.parent))}" alt="{html.escape(label)}">
        <h2>{html.escape(label)}</h2>
        <p>{html.escape(filename)}</p>
      </article>""")
        else:
            cards.append(f"""
      <article class="card missing">
        <div class="placeholder">Missing</div>
        <h2>{html.escape(label)}</h2>
        <p>{html.escape(filename)}</p>
      </article>""")

    title_candidates = titles.get("titles", titles if isinstance(titles, list) else [])
    title_list = "".join(f"<li>{html.escape(str(item))}</li>" for item in title_candidates)
    key_elements = ", ".join(str(item) for item in analysis.get("key_elements", []))

    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Video Cover Review</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #101214;
      --panel: #181b1f;
      --text: #f5f7fa;
      --muted: #a7b0bb;
      --line: #30363d;
      --accent: #ffd640;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    header {{
      padding: 32px clamp(18px, 5vw, 56px) 18px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{ margin: 0 0 10px; font-size: clamp(28px, 5vw, 48px); }}
    .meta {{ color: var(--muted); line-height: 1.7; max-width: 980px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 18px;
      padding: 24px clamp(18px, 5vw, 56px) 40px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    .card img, .placeholder {{
      display: block;
      width: 100%;
      aspect-ratio: 3 / 4;
      object-fit: cover;
      background: #22272e;
    }}
    .placeholder {{
      display: grid;
      place-items: center;
      color: var(--muted);
    }}
    .card h2 {{ margin: 14px 14px 4px; font-size: 20px; }}
    .card p {{ margin: 0 14px 16px; color: var(--muted); }}
    section {{
      padding: 0 clamp(18px, 5vw, 56px) 48px;
      color: var(--muted);
    }}
    code {{ color: var(--accent); }}
    @media (max-width: 900px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(selected_title or "Video Cover Review")}</h1>
    <div class="meta">
      <div>类型：<code>{html.escape(str(analysis.get("video_type", "")))}</code></div>
      <div>主体策略：<code>{html.escape(str(analysis.get("subject_strategy", "")))}</code></div>
      <div>关键元素：{html.escape(key_elements)}</div>
      <div>摘要：{html.escape(str(analysis.get("content_summary", "")))}</div>
    </div>
  </header>
  <main class="grid">
    {''.join(cards)}
  </main>
  <section>
    <h2>标题候选</h2>
    <ol>{title_list}</ol>
    <h2>质量检查</h2>
    <pre>{html.escape(json.dumps(quality, ensure_ascii=False, indent=2))}</pre>
  </section>
</body>
</html>
"""
    output.write_text(page, encoding="utf-8")


if __name__ == "__main__":
    main()
