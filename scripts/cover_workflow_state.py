#!/usr/bin/env python3
"""Persist the non-negotiable decisions in a video-cover job.

This script does not generate images. It prevents an agent from silently
skipping the portrait/title gates or making a landscape cover before a user has
selected the matching portrait cover.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 2


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path):
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def write_json(path, payload):
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_job(path):
    job = read_json(path)
    if job.get("schema_version") != SCHEMA_VERSION:
        raise SystemExit("Unsupported cover job schema. Create a new job with init.")
    return job


def update_phase(job):
    if job.get("person_required") and not job.get("person_mode"):
        job["phase"] = "awaiting_person_choice"
    elif not job.get("copy"):
        job["phase"] = "awaiting_title_choice"
    elif not job.get("selected_vertical"):
        job["phase"] = "ready_for_vertical_generation"
    elif not job.get("landscape_candidates"):
        job["phase"] = "ready_for_landscape_generation"
    elif not job.get("selected_landscape"):
        job["phase"] = "awaiting_landscape_selection"
    else:
        job["phase"] = "complete"


def command_init(args):
    job_path = Path(args.job).expanduser()
    video = Path(args.video).expanduser().resolve()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "created_at": now(),
        "updated_at": now(),
        "video": str(video),
        "analysis": "",
        "person_required": False,
        "person_mode": "",
        "portrait": "",
        "pose_reference": "",
        "copy": None,
        "vertical_candidates": [],
        "selected_vertical": None,
        "landscape_candidates": [],
        "selected_landscape": None,
        "phase": "awaiting_analysis",
        "history": [{"at": now(), "event": "job_created"}],
    }
    write_json(job_path, payload)
    print(job_path)


def command_record_analysis(args):
    job = load_job(args.job)
    analysis_path = Path(args.analysis).expanduser().resolve()
    analysis = read_json(analysis_path)
    job["analysis"] = str(analysis_path)
    job["person_required"] = bool(analysis.get("has_real_person"))
    job["portrait_frame_quality"] = analysis.get("portrait_frame_quality", "poor")
    job["pose_reference"] = str(analysis.get("pose_reference_frame", "") or "")
    job["content_references"] = [str(item) for item in analysis.get("content_reference_frames", []) if str(item)]
    job["updated_at"] = now()
    job["history"].append({"at": now(), "event": "analysis_recorded", "has_real_person": job["person_required"]})
    update_phase(job)
    write_json(args.job, job)
    print(job["phase"])


def command_choose_person(args):
    job = load_job(args.job)
    mode = args.mode
    portrait = str(Path(args.portrait).expanduser().resolve()) if args.portrait else ""
    pose_reference = (
        str(Path(args.pose_reference).expanduser().resolve())
        if args.pose_reference else (job.get("pose_reference", "") or portrait)
    )
    if job.get("person_required") and mode == "auto":
        raise SystemExit("A real presenter was detected. Choose uploaded-photo, frame-cutout, or no-person explicitly.")
    if mode in {"uploaded-photo", "frame-cutout"}:
        if not portrait:
            raise SystemExit(f"{mode} requires --portrait.")
        if not Path(portrait).exists():
            raise SystemExit(f"Portrait file not found: {portrait}")
    if mode == "frame-cutout" and job.get("portrait_frame_quality") != "good":
        raise SystemExit("The selected video frame is not reliable enough for a portrait. Ask for an uploaded photo or use no-person.")
    if pose_reference and not Path(pose_reference).exists():
        raise SystemExit(f"Pose reference file not found: {pose_reference}")
    job["person_mode"] = mode
    job["portrait"] = portrait
    job["pose_reference"] = pose_reference
    job["updated_at"] = now()
    job["history"].append({"at": now(), "event": "person_mode_selected", "mode": mode})
    update_phase(job)
    write_json(args.job, job)
    print(job["phase"])


def command_choose_title(args):
    job = load_job(args.job)
    if job.get("person_required") and not job.get("person_mode"):
        raise SystemExit("Choose the portrait strategy before confirming the title.")
    title = args.title.strip()
    hook = args.hook.strip()
    subtitle = args.subtitle.strip()
    if not title:
        raise SystemExit("--title is required.")
    if not hook:
        raise SystemExit("--hook is required. Use a concise click reason, not an empty placeholder.")
    job["copy"] = {"title": title, "hook": hook, "subtitle": subtitle}
    job["updated_at"] = now()
    job["history"].append({"at": now(), "event": "copy_confirmed", "copy": job["copy"]})
    update_phase(job)
    write_json(args.job, job)
    print(job["phase"])


def command_register_candidate(args):
    job = load_job(args.job)
    ratio = args.ratio
    image = Path(args.image).expanduser().resolve()
    if not image.exists():
        raise SystemExit(f"Candidate image not found: {image}")
    candidate = {"route": args.route, "image": str(image), "manifest": args.manifest or "", "registered_at": now()}
    field = "vertical_candidates" if ratio == "3:4" else "landscape_candidates"
    job[field] = [item for item in job.get(field, []) if item.get("image") != str(image)] + [candidate]
    job["updated_at"] = now()
    job["history"].append({"at": now(), "event": "candidate_registered", "ratio": ratio, "route": args.route})
    update_phase(job)
    write_json(args.job, job)
    print(job["phase"])


def find_candidate(candidates, image, route):
    wanted = str(Path(image).expanduser().resolve()) if image else ""
    for item in candidates:
        if wanted and item.get("image") == wanted:
            return item
        if route and item.get("route") == route:
            return item
    return None


def command_select_vertical(args):
    job = load_job(args.job)
    candidate = find_candidate(job.get("vertical_candidates", []), args.image, args.route)
    if not candidate:
        raise SystemExit("Select one registered 3:4 candidate. Register the actual generated image first.")
    job["selected_vertical"] = candidate
    job["updated_at"] = now()
    job["history"].append({"at": now(), "event": "vertical_selected", "route": candidate["route"], "image": candidate["image"]})
    update_phase(job)
    write_json(args.job, job)
    print(job["phase"])


def command_select_landscape(args):
    job = load_job(args.job)
    candidate = find_candidate(job.get("landscape_candidates", []), args.image, args.route)
    if not candidate:
        raise SystemExit("Select one registered 4:3 candidate. Register the actual generated image first.")
    job["selected_landscape"] = candidate
    job["updated_at"] = now()
    job["history"].append({"at": now(), "event": "landscape_selected", "route": candidate["route"], "image": candidate["image"]})
    update_phase(job)
    write_json(args.job, job)
    print(job["phase"])


def command_assert_ready(args):
    job = load_job(args.job)
    expected = "ready_for_vertical_generation" if args.ratio == "3:4" else "ready_for_landscape_generation"
    if job.get("phase") != expected:
        raise SystemExit(f"Cannot generate {args.ratio}; job phase is {job.get('phase')}, expected {expected}.")
    if args.ratio == "4:3" and not job.get("selected_vertical"):
        raise SystemExit("Cannot generate 4:3 without a selected 3:4 cover.")
    print("ready")


def command_show(args):
    print(json.dumps(load_job(args.job), ensure_ascii=False, indent=2))


def build_parser():
    parser = argparse.ArgumentParser(description="State machine for a video-cover job.")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--job", required=True)
    init.add_argument("--video", required=True)
    init.set_defaults(func=command_init)
    analysis = sub.add_parser("record-analysis")
    analysis.add_argument("--job", required=True)
    analysis.add_argument("--analysis", required=True)
    analysis.set_defaults(func=command_record_analysis)
    person = sub.add_parser("choose-person")
    person.add_argument("--job", required=True)
    person.add_argument("--mode", required=True, choices=["uploaded-photo", "frame-cutout", "no-person", "auto"])
    person.add_argument("--portrait", default="")
    person.add_argument("--pose-reference", default="", help="Original full frame/photo for Dreamina pose and wardrobe grounding.")
    person.set_defaults(func=command_choose_person)
    title = sub.add_parser("choose-title")
    title.add_argument("--job", required=True)
    title.add_argument("--title", required=True)
    title.add_argument("--hook", required=True)
    title.add_argument("--subtitle", default="")
    title.set_defaults(func=command_choose_title)
    candidate = sub.add_parser("register-candidate")
    candidate.add_argument("--job", required=True)
    candidate.add_argument("--ratio", required=True, choices=["3:4", "4:3"])
    candidate.add_argument("--route", required=True)
    candidate.add_argument("--image", required=True)
    candidate.add_argument("--manifest", default="")
    candidate.set_defaults(func=command_register_candidate)
    vertical = sub.add_parser("select-vertical")
    vertical.add_argument("--job", required=True)
    vertical.add_argument("--image", default="")
    vertical.add_argument("--route", default="")
    vertical.set_defaults(func=command_select_vertical)
    landscape = sub.add_parser("select-landscape")
    landscape.add_argument("--job", required=True)
    landscape.add_argument("--image", default="")
    landscape.add_argument("--route", default="")
    landscape.set_defaults(func=command_select_landscape)
    ready = sub.add_parser("assert-ready")
    ready.add_argument("--job", required=True)
    ready.add_argument("--ratio", required=True, choices=["3:4", "4:3"])
    ready.set_defaults(func=command_assert_ready)
    show = sub.add_parser("show")
    show.add_argument("--job", required=True)
    show.set_defaults(func=command_show)
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.func(args)
