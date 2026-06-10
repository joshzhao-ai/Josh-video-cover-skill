#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_ROOT = Path.home() / "Desktop" / "video-covers"
DEFAULT_LAYOUT_REFERENCE = Path("/Users/bytedance/Desktop/OpenClaw封面_4比3 1.png")
VARIANTS = ("info-heavy", "visual-heavy", "balanced")
STOP_STAGES = ("frames", "analysis", "gate", "prompts", "covers", "review", "landscape", "done")


class UserChoiceNeeded(Exception):
    def __init__(self, message, choices=None):
        super().__init__(message)
        self.choices = choices or []


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def print_step(message):
    print(f"\n==> {message}", flush=True)


def ensure_api_env():
    if os.environ.get("ARK_API_KEY"):
        os.environ.setdefault("VCG_VLM_API_KEY", os.environ["ARK_API_KEY"])
        os.environ.setdefault("VCG_IMAGE_API_KEY", os.environ["ARK_API_KEY"])
    os.environ.setdefault("VCG_VLM_MODEL", "doubao-seed-2-0-pro-260215")
    os.environ.setdefault("VCG_IMAGE_MODEL", "doubao-seedream-5-0-260128")
    os.environ.setdefault("VCG_IMAGE_SIZE", "2K")


def run_cmd(args, env=None):
    printable = " ".join(str(item) for item in args)
    print(f"$ {printable}", flush=True)
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    subprocess.run([str(item) for item in args], check=True, env=merged_env)


def make_workdir(video, output_root, workdir):
    if workdir:
        path = Path(workdir).expanduser().resolve()
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path(output_root).expanduser().resolve() / f"{Path(video).stem}_{timestamp}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def all_exist(paths):
    return all(Path(path).exists() for path in paths)


def should_stop(stage, args, state):
    if args.stop_after == stage:
        state["status"] = f"stopped_after_{stage}"
        write_json(state["paths"]["workflow_state"], state)
        build_report(Path(state["workdir"]), state)
        raise SystemExit(0)


def prompt_select(label, choices, default_index=0):
    if not sys.stdin.isatty():
        raise UserChoiceNeeded(f"需要选择 {label}", choices)
    print(f"\n请选择 {label}:")
    for index, choice in enumerate(choices, start=1):
        print(f"{index}. {choice}")
    raw = input(f"输入序号，默认 {default_index + 1}: ").strip()
    if not raw:
        return default_index
    value = int(raw) - 1
    if value < 0 or value >= len(choices):
        raise SystemExit(f"选择超出范围: {raw}")
    return value


def title_candidates(titles_payload):
    candidates = titles_payload.get("title_candidates") or []
    normalized = []
    if candidates:
        for item in candidates[:3]:
            normalized.append({
                "title": str(item.get("title", "")).strip(),
                "subtitle": str(item.get("subtitle", "")).strip(),
                "reason": str(item.get("reason", "")).strip(),
                "hook_type": str(item.get("hook_type", "")).strip(),
            })
    else:
        titles = titles_payload.get("titles", [])[:3]
        subtitles = titles_payload.get("subtitles", [])[:3]
        for index, title in enumerate(titles):
            normalized.append({
                "title": str(title).strip(),
                "subtitle": str(subtitles[index]).strip() if index < len(subtitles) else "",
                "reason": "",
                "hook_type": "",
            })
    return [item for item in normalized if item["title"]]


def choose_title(args, workdir, state):
    candidates = title_candidates(read_json(workdir / "titles.json"))
    if not candidates:
        raise SystemExit("No title candidates found.")

    if args.title:
        selected = {"title": args.title, "subtitle": args.subtitle or "", "reason": "provided by user", "hook_type": ""}
    elif args.title_index:
        index = args.title_index - 1
        if index < 0 or index >= len(candidates):
            raise SystemExit(f"--title-index must be between 1 and {len(candidates)}")
        selected = candidates[index]
    elif args.auto:
        selected = candidates[0]
    else:
        labels = [
            f"{item['title']} / {item.get('subtitle', '')} ({item.get('hook_type', '')}) {item.get('reason', '')}"
            for item in candidates
        ]
        index = prompt_select("标题", labels, 0)
        selected = candidates[index]

    if args.subtitle:
        selected["subtitle"] = args.subtitle
    write_text(workdir / "selected_title.txt", selected["title"])
    write_json(workdir / "selected_title.json", selected)
    state["selection"]["title"] = selected
    return selected


def choose_person_mode(args, workdir, state):
    gate = read_json(workdir / "person_asset_gate.json")
    requires = bool(gate.get("requires_decision"))
    mode = args.person_mode
    reference = args.person_reference

    if requires and mode == "auto":
        if args.auto:
            mode = gate.get("safe_default", "no-person")
        else:
            choices = [
                f"{item['id']} - {item['description']}"
                for item in gate.get("options", [])
            ]
            if gate.get("experimental_options"):
                choices.extend([
                    f"{item['id']} - {item['description']}"
                    for item in gate.get("experimental_options", [])
                ])
            index = prompt_select("人物策略", choices, 1 if len(choices) > 1 else 0)
            mode = (gate.get("options", []) + gate.get("experimental_options", []))[index]["id"]

    if requires and mode == "uploaded-photo" and not reference:
        raise UserChoiceNeeded("需要用户上传本人照片路径，才能走 uploaded-photo。", ["uploaded-photo", "no-person"])

    if requires and mode == "video-frame":
        recommended = read_json(workdir / "analysis.json").get("recommended_frame", "")
        frame = workdir / recommended if recommended.startswith("frames/") else Path(recommended)
        if not frame.exists():
            frame = workdir / "frames" / "frame_05.jpg"
        reference = str(workdir / "person_reference.jpg")
        run_cmd([
            sys.executable,
            SCRIPT_DIR / "extract_person_reference.py",
            "--frame",
            frame,
            "--output",
            reference,
        ])

    if not requires and mode == "auto":
        reference = reference or ""

    choice = {
        "person_mode": mode,
        "person_reference": str(Path(reference).expanduser().resolve()) if reference else "",
        "requires_decision": requires,
        "note": "video-frame is experimental" if mode == "video-frame" else "",
    }
    write_json(workdir / "person_asset_choice.json", choice)
    state["selection"]["person"] = choice
    return choice


def choose_cover_variant(args, workdir, state):
    if args.cover_variant:
        variant = args.cover_variant
    elif args.auto:
        variant = "balanced"
    else:
        labels = [f"{name}: {workdir / 'covers-seedream-text' / (name + '.jpg')}" for name in VARIANTS]
        variant = VARIANTS[prompt_select("3:4 封面", labels, 2)]
    cover = workdir / "covers-seedream-text" / f"{variant}.jpg"
    if not cover.exists():
        raise SystemExit(f"Selected cover not found: {cover}")
    write_text(workdir / "selected_cover.txt", str(cover))
    state["selection"]["cover_variant"] = variant
    state["selection"]["cover"] = str(cover)
    return variant, cover


def create_preview(covers_dir):
    files = [covers_dir / f"{name}.jpg" for name in VARIANTS]
    if not all_exist(files):
        return None
    thumbs = []
    for path in files:
        image = Image.open(path).convert("RGB")
        image.thumbnail((360, 480), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (360, 520), (18, 18, 22))
        canvas.paste(image, ((360 - image.width) // 2, 0))
        ImageDraw.Draw(canvas).text((12, 490), path.stem, fill=(255, 255, 255))
        thumbs.append(canvas)
    preview = Image.new("RGB", (360 * len(thumbs), 520), (12, 12, 16))
    for index, thumb in enumerate(thumbs):
        preview.paste(thumb, (index * 360, 0))
    output = covers_dir / "preview.jpg"
    preview.save(output, quality=92)
    return output


def source_text(analysis, title):
    return " ".join([
        title or "",
        analysis.get("content_summary", ""),
        analysis.get("hook_summary", ""),
        " ".join(map(str, analysis.get("key_elements", []))),
    ]).lower()


def auto_subject_description(analysis, title, person_choice, retry_report=None):
    detected = retry_report.get("detected", {}) if retry_report else {}
    portrait_subject = detected.get("portrait_subject")
    if portrait_subject:
        return f"必须保留选中 3:4 封面的核心主体：{portrait_subject}。不要把主体换成另一种符号、人物或产品。"
    text = source_text(analysis, title)
    if "openclaw" in text:
        return (
            "必须以选中的 3:4 封面作为唯一视觉身份来源，保留它的核心识别元素：红色机械钳爪、"
            "深蓝黑科技背景、青色节点光、代码/浏览器/AI 调度界面氛围、金白描边标题风格。"
            "横版可以为了缩略图构图把红色机械钳爪调整为更大的前景姿态或机械臂钳爪，"
            "但只能做同一 OpenClaw 红色金属钳爪家族内的重构，不能换成另一种主体。"
            "如果竖版有明显的蓝色能量核心、节点网络或全息面板，要尽量保留为同一套视觉系统的线索。"
            "不要变成圆环装置、普通机器人手掌、无关吉祥物或人物；主视觉要有 40-60% 画面锚点和强烈前景压迫感。"
        )
    if person_choice.get("person_mode") == "uploaded-photo":
        return "保留用户上传本人照片的人物身份、五官特征和专业气质，背景可以重构，但人物不能变成陌生人。"
    if person_choice.get("person_mode") == "no-person":
        return "保留选中 3:4 封面的无人物主题符号、核心图形、数据/趋势/界面元素，不要出现真人、人脸或半身像。"
    return "保留选中 3:4 封面的核心主体、产品或符号，不能改成另一种主体。"


def auto_style_description(analysis, title, retry_report=None):
    detected = retry_report.get("detected", {}) if retry_report else {}
    if detected.get("portrait_subject"):
        return "延续选中 3:4 封面的色彩、光效、材质、标题字效和背景信息层，保证像同一套封面系统。"
    text = source_text(analysis, title)
    if "openclaw" in text:
        return "延续选中 3:4 封面的深蓝黑科技背景、青色节点光、金白描边标题、红色金属钳爪材质和发光蓝色核心。"
    return "延续选中 3:4 封面的主色、光效、背景信息层、标题字效和高级缩略图质感。"


def extra_from_retry(report):
    if not report:
        return ""
    pieces = []
    recommendation = report.get("recommendation")
    if recommendation:
        pieces.append(f"根据一致性质检修正：{recommendation}")
    critical = report.get("critical_issues") or []
    if critical:
        pieces.append("必须修复这些致命问题：" + "；".join(map(str, critical)))
    return "".join(pieces)


def generate_landscape(args, workdir, title, subtitle, cover, analysis, person_choice, attempt, retry_report=None):
    layout_reference = Path(args.layout_reference).expanduser().resolve() if args.layout_reference else DEFAULT_LAYOUT_REFERENCE
    output_dir = workdir / "landscape-4x3"
    output_dir.mkdir(parents=True, exist_ok=True)
    if attempt == 0:
        image_output = output_dir / "landscape.jpg"
        prompt_output = output_dir / "landscape.prompt.json"
    else:
        image_output = output_dir / f"landscape.retry{attempt}.jpg"
        prompt_output = output_dir / f"landscape.retry{attempt}.prompt.json"

    if attempt == 0 and image_output.exists() and not args.force:
        print(f"Reuse existing landscape: {image_output}", flush=True)
        return image_output

    command = [
        sys.executable,
        SCRIPT_DIR / "generate_landscape_from_cover.py",
        "--cover",
        cover,
        "--output",
        image_output,
        "--prompt-output",
        prompt_output,
        "--title",
        title,
        "--subtitle",
        subtitle,
        "--source-variant",
        f"{workdir.name}-attempt{attempt}",
        "--subject-description",
        args.subject_description or auto_subject_description(analysis, title, person_choice, retry_report),
        "--style-description",
        args.style_description or auto_style_description(analysis, title, retry_report),
        "--layout",
        args.landscape_layout,
        "--extra",
        "主标题必须巨大清晰但留安全边距；副标题作为清晰横向标签。" + extra_from_retry(retry_report),
    ]
    if layout_reference.exists():
        command.extend(["--layout-reference", layout_reference])
    run_cmd(command)
    if attempt > 0:
        shutil.copy2(image_output, output_dir / "landscape.jpg")
        shutil.copy2(prompt_output, output_dir / "landscape.prompt.json")
    return output_dir / "landscape.jpg"


def run_consistency(workdir, title, subtitle, cover, landscape, attempt):
    output = workdir / "consistency.cross-format.json"
    if attempt > 0:
        output = workdir / f"consistency.cross-format.retry{attempt}.json"
    run_cmd([
        sys.executable,
        SCRIPT_DIR / "check_cross_format_consistency.py",
        "--portrait",
        cover,
        "--landscape",
        landscape,
        "--output",
        output,
        "--title",
        title,
        "--subtitle",
        subtitle,
    ])
    report = read_json(output)
    if attempt > 0:
        shutil.copy2(output, workdir / "consistency.cross-format.json")
    return report


def build_report(workdir, state):
    title = state.get("selection", {}).get("title", {})
    person = state.get("selection", {}).get("person", {})
    report = {
        "status": state.get("status", "completed"),
        "workdir": str(workdir),
        "title": title,
        "person": person,
        "cover_variant": state.get("selection", {}).get("cover_variant"),
        "paths": {
            "review": str(workdir / "review.seedream.text.html"),
            "preview": str(workdir / "covers-seedream-text" / "preview.jpg"),
            "selected_cover": state.get("selection", {}).get("cover", ""),
            "landscape": str(workdir / "landscape-4x3" / "landscape.jpg"),
            "quality": str(workdir / "quality.seedream.text.json"),
            "consistency": str(workdir / "consistency.cross-format.json"),
            "workflow_state": str(workdir / "workflow_state.json"),
        },
    }
    write_json(workdir / "workflow_report.json", report)
    md = [
        "# Video Cover Workflow Report",
        "",
        f"- Status: `{report['status']}`",
        f"- Workdir: `{workdir}`",
        f"- Title: `{title.get('title', '')}`",
        f"- Subtitle: `{title.get('subtitle', '')}`",
        f"- Person mode: `{person.get('person_mode', '')}`",
        f"- 3:4 variant: `{report.get('cover_variant', '')}`",
        "",
        "## Outputs",
        "",
        f"- Review: `{report['paths']['review']}`",
        f"- Preview: `{report['paths']['preview']}`",
        f"- Selected 3:4: `{report['paths']['selected_cover']}`",
        f"- Landscape 4:3: `{report['paths']['landscape']}`",
        f"- Quality: `{report['paths']['quality']}`",
        f"- Consistency: `{report['paths']['consistency']}`",
    ]
    write_text(workdir / "workflow_report.md", "\n".join(md) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description="Run the full video cover workflow end to end.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--workdir")
    parser.add_argument("--frame-count", type=int, default=12)
    parser.add_argument("--language", default="zh")
    parser.add_argument("--auto", action="store_true", help="Choose safe defaults and run without prompts.")
    parser.add_argument("--force", action="store_true", help="Rerun steps even when outputs exist.")
    parser.add_argument("--stop-after", choices=STOP_STAGES, default="done")
    parser.add_argument("--title")
    parser.add_argument("--subtitle")
    parser.add_argument("--title-index", type=int, help="1-based title candidate index.")
    parser.add_argument("--person-mode", choices=["auto", "uploaded-photo", "no-person", "video-frame"], default="auto")
    parser.add_argument("--person-reference")
    parser.add_argument("--cover-variant", choices=VARIANTS)
    parser.add_argument("--no-landscape", action="store_true")
    parser.add_argument("--layout-reference")
    parser.add_argument("--landscape-layout", choices=["title-left-hero-right", "center-hero-left-title", "reference-mega-title"], default="reference-mega-title")
    parser.add_argument("--subject-description", default="")
    parser.add_argument("--style-description", default="")
    parser.add_argument("--landscape-retries", type=int, default=1)
    parser.add_argument("--no-consistency", action="store_true")
    args = parser.parse_args()

    ensure_api_env()
    video = Path(args.video).expanduser().resolve()
    if not video.exists():
        raise SystemExit(f"Video not found: {video}")
    workdir = make_workdir(video, args.output_root, args.workdir)
    state = {
        "status": "running",
        "video": str(video),
        "workdir": str(workdir),
        "selection": {},
        "paths": {
            "workflow_state": str(workdir / "workflow_state.json"),
        },
    }
    write_json(workdir / "workflow_state.json", state)

    try:
        print_step("Extract frames")
        if args.force or not (workdir / "frames" / "index.json").exists():
            run_cmd([
                sys.executable,
                SCRIPT_DIR / "extract_frames.py",
                "--video",
                video,
                "--output-dir",
                workdir / "frames",
                "--count",
                str(args.frame_count),
            ])
        should_stop("frames", args, state)

        print_step("Analyze video")
        if args.force or not all_exist([workdir / "analysis.json", workdir / "titles.json"]):
            run_cmd([
                sys.executable,
                SCRIPT_DIR / "analyze_with_vlm.py",
                "--frames-dir",
                workdir / "frames",
                "--analysis-output",
                workdir / "analysis.json",
                "--titles-output",
                workdir / "titles.json",
                "--language",
                args.language,
                "--max-frames",
                str(args.frame_count),
            ])
        analysis = read_json(workdir / "analysis.json")
        should_stop("analysis", args, state)

        print_step("Run person gate")
        if args.force or not (workdir / "person_asset_gate.json").exists():
            run_cmd([
                sys.executable,
                SCRIPT_DIR / "person_asset_gate.py",
                "--analysis",
                workdir / "analysis.json",
                "--output",
                workdir / "person_asset_gate.json",
            ])
        person_choice = choose_person_mode(args, workdir, state)
        should_stop("gate", args, state)

        print_step("Choose title")
        selected_title = choose_title(args, workdir, state)
        title = selected_title["title"]
        subtitle = selected_title.get("subtitle", "")

        print_step("Build prompts")
        prompt_cmd = [
            sys.executable,
            SCRIPT_DIR / "build_cover_prompts.py",
            "--analysis",
            workdir / "analysis.json",
            "--title-file",
            workdir / "selected_title.txt",
            "--output",
            workdir / "prompts.seedream.text.json",
            "--language",
            args.language,
            "--subtitle",
            subtitle,
            "--text-mode",
            "model",
            "--person-mode",
            person_choice["person_mode"],
        ]
        if person_choice.get("person_reference"):
            prompt_cmd.extend(["--person-reference", person_choice["person_reference"]])
        if args.force or not (workdir / "prompts.seedream.text.json").exists():
            run_cmd(prompt_cmd)
        should_stop("prompts", args, state)

        print_step("Generate 3:4 covers")
        covers_dir = workdir / "covers-seedream-text"
        expected_covers = [covers_dir / f"{name}.jpg" for name in VARIANTS]
        if args.force or not all_exist(expected_covers):
            image_env = {}
            cover_cmd = [
                sys.executable,
                SCRIPT_DIR / "generate_ai_covers.py",
                "--prompts",
                workdir / "prompts.seedream.text.json",
                "--output-dir",
                covers_dir,
            ]
            if person_choice.get("person_reference") and person_choice["person_mode"] in {"uploaded-photo", "video-frame"}:
                cover_cmd.extend(["--reference-frame", person_choice["person_reference"]])
                image_env["VCG_IMAGE_INCLUDE_REFERENCE"] = "1"
            run_cmd(cover_cmd, env=image_env)
        create_preview(covers_dir)
        should_stop("covers", args, state)

        print_step("Quality and review")
        run_cmd([
            sys.executable,
            SCRIPT_DIR / "check_quality.py",
            "--covers-dir",
            covers_dir,
            "--output",
            workdir / "quality.seedream.text.json",
        ])
        run_cmd([
            sys.executable,
            SCRIPT_DIR / "generate_review_page.py",
            "--workdir",
            workdir,
            "--covers-dir",
            covers_dir,
            "--quality",
            workdir / "quality.seedream.text.json",
            "--output",
            workdir / "review.seedream.text.html",
        ])
        should_stop("review", args, state)

        if not args.no_landscape:
            print_step("Generate 4:3 landscape")
            variant, cover = choose_cover_variant(args, workdir, state)
            landscape = None
            retry_report = None
            consistency = None
            for attempt in range(args.landscape_retries + 1):
                landscape = generate_landscape(args, workdir, title, subtitle, cover, analysis, person_choice, attempt, retry_report)
                if args.no_consistency:
                    break
                consistency = run_consistency(workdir, title, subtitle, cover, landscape, attempt)
                if consistency.get("passed"):
                    break
                retry_report = consistency
            if consistency:
                state["consistency"] = consistency
        should_stop("landscape", args, state)

        state["status"] = "completed"
        write_json(workdir / "workflow_state.json", state)
        report = build_report(workdir, state)
        print_step("Completed")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except UserChoiceNeeded as exc:
        state["status"] = "needs_user_choice"
        state["message"] = str(exc)
        state["choices"] = exc.choices
        write_json(workdir / "workflow_state.json", state)
        build_report(workdir, state)
        print(f"\n需要用户选择：{exc}", file=sys.stderr)
        if exc.choices:
            for choice in exc.choices:
                print(f"- {choice}", file=sys.stderr)
        raise SystemExit(2)
    except subprocess.CalledProcessError as exc:
        state["status"] = "failed"
        state["message"] = f"Command failed with exit code {exc.returncode}: {' '.join(map(str, exc.cmd))}"
        write_json(workdir / "workflow_state.json", state)
        build_report(workdir, state)
        raise


if __name__ == "__main__":
    main()
