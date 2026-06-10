#!/usr/bin/env python3
import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path


def run_json(command):
    result = subprocess.run(command, check=True, text=True, capture_output=True)
    return json.loads(result.stdout)


def probe_duration(video_path):
    data = run_json([
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(video_path),
    ])
    return float(data["format"]["duration"])


def main():
    parser = argparse.ArgumentParser(description="Extract evenly spaced frames from a video.")
    parser.add_argument("--video", required=True, help="Path to a local video file.")
    parser.add_argument("--output-dir", required=True, help="Directory for extracted frames.")
    parser.add_argument("--count", type=int, default=12, help="Number of frames to extract.")
    args = parser.parse_args()

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise SystemExit("ffmpeg and ffprobe are required.")

    video_path = Path(args.video).expanduser().resolve()
    if not video_path.exists():
        raise SystemExit(f"Video not found: {video_path}")
    if args.count < 1:
        raise SystemExit("--count must be at least 1.")

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    duration = max(probe_duration(video_path), 0.1)
    start = min(0.5, duration / 3)
    end = max(duration - 0.5, start)
    step = (end - start) / max(args.count - 1, 1)

    frames = []
    for index in range(args.count):
        timestamp = start + step * index
        frame_path = output_dir / f"frame_{index:02d}.jpg"
        subprocess.run([
            "ffmpeg",
            "-y",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(frame_path),
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        frames.append({
            "index": index,
            "timestamp": round(timestamp, 3),
            "path": str(frame_path),
        })

    (output_dir / "index.json").write_text(json.dumps({
        "video": str(video_path),
        "duration": round(duration, 3),
        "count": len(frames),
        "frames": frames,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
