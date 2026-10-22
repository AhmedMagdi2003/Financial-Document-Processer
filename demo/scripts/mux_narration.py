"""Mux the English narration into the recorded demo without re-encoding video."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="demo/output/finance_agent_demo_silent.mp4")
    parser.add_argument("--audio", default="demo/output/finance_agent_narration_en.mp3")
    parser.add_argument("--output", default="demo/output/finance_agent_demo.mp4")
    parser.add_argument("--duration", type=int, default=84)
    args = parser.parse_args()
    source = ROOT / args.input
    narration = ROOT / args.audio
    destination = ROOT / args.output
    if not source.is_file() or not narration.is_file():
        raise FileNotFoundError("Both the recorded MP4 and English narration must exist")
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing video: {destination}")
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-i",
            str(narration),
            "-filter_complex",
            "[1:a]adelay=1500:all=1,apad[a]",
            "-map",
            "0:v:0",
            "-map",
            "[a]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-shortest",
            "-t",
            str(args.duration),
            "-movflags",
            "+faststart",
            str(destination),
        ],
        check=True,
    )
    print(f"Narrated MP4: {destination}")


if __name__ == "__main__":
    main()
