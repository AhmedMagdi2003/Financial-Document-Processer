"""Create a concise narrated walkthrough from the user's full screen recording."""

from __future__ import annotations

import argparse
import asyncio
import re
import subprocess
from pathlib import Path

import edge_tts
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[2]
VOICE = "en-US-AriaNeural"
RATE = "+0%"

# Keep each distinct workflow visible; shorten waiting, repeated scrolling, and
# file-picker dwell time. Speeds are conservative enough to keep the UI legible.
SEGMENTS = [
    (0.0, 11.0, 1.7),       # Sign-in and workspace entry
    (14.0, 45.0, 1.5),     # USD/EUR/EGP reporting and exchange-rate details
    (52.0, 85.0, 1.8),     # Upload flow, batch processing, Drive intake
    (85.0, 112.0, 1.8),   # Extraction result and original-document review
    (130.0, 165.0, 1.8),  # Review queue, duplicate/validation evidence
    (170.0, 193.0, 2.0),  # Reviewing a second document and its decision
    (205.0, 225.0, 1.8),  # Return to the document/review workflow
    (225.0, 289.0, 1.8),  # Image invoice, corrections, revalidation, confirmation
    (289.0, 308.0, 1.8),  # Updated finance dashboard and operations
    (308.0, 329.0, 1.8),  # Categories and projects
    (329.0, 356.0, 1.8),  # Integrations and Google Sheets result
]

NARRATION = """Welcome to Impact Finance. This walkthrough follows a document from intake through review, recording, reporting, and spreadsheet delivery.

At the top of the finance dashboard, choose US dollars, euros, or Egyptian pounds as the reporting currency. Confirmed spending, categories, and monthly trends convert together, while each expense keeps its original invoice currency and amount. The exchange-rate panel shows the currency pairs, provider, and rate update date, so the conversion is transparent.

Select a project and upload invoices or receipts as PDFs and images, one at a time or in a batch. Documents can also arrive through the connected Google Drive intake. Processing status appears as the batch moves through the queue.

For each document, compare the original with the extracted vendor, date, invoice number, totals, tax, discount, and currency. The system keeps supporting evidence with the result. Clear records can be automatically recorded when that option is enabled; uncertain fields and possible duplicates are held for a person to review.

On the review screen, inspect the original page, correct values that are missing or misread, choose a category, and revalidate. The validation panel explains issues such as missing currency or a possible duplicate. A reviewer can confirm a corrected record or dismiss a document, with a reason when required. This keeps unverified expenses out of confirmed spending until a human decision is made.

Once confirmed, records appear in the expense tracker and the totals and charts update. The reporting-currency selector changes the view without rewriting source records. The Operations page provides pipeline status, processing stages, events, and estimated model spend, making it easier to investigate a run.

Automatic extraction is not the final authority: original previews and supporting page evidence remain available, and validation checks amounts, currency, dates, and possible duplicates. When a value cannot be verified, the review queue makes that uncertainty visible instead of quietly adding it to confirmed totals. The expense tracker can be filtered by project, category, source currency, and date, while Operations keeps a traceable run history.

Categories and projects can be maintained in the workspace. The Integrations page documents the shared-folder Drive workflow and Google Sheets projection, along with other automation options. Here, the synced expense rows are visible in the spreadsheet.

That is the complete flow: bring documents in, review evidence, confirm records, and track spending consistently across currencies."""


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


async def render_voice(path: Path) -> None:
    await edge_tts.Communicate(NARRATION, voice=VOICE, rate=RATE).save(str(path))


def build_video(source: Path, narration: Path, output: Path, silent: Path) -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    if not source.is_file():
        raise FileNotFoundError(source)
    if output.exists() or silent.exists():
        raise FileExistsError("Refusing to overwrite an existing video deliverable")

    split_labels = "".join(f"[v{i}]" for i in range(len(SEGMENTS)))
    filters = [f"[0:v]split={len(SEGMENTS)}{split_labels}"]
    trimmed = []
    for index, (start, end, speed) in enumerate(SEGMENTS):
        label = f"[clip{index}]"
        filters.append(
            f"[v{index}]trim=start={start}:end={end},"
            f"setpts=(PTS-STARTPTS)/{speed}{label}"
        )
        trimmed.append(label)
    filters.append(f"{''.join(trimmed)}concat=n={len(SEGMENTS)}:v=1:a=0[outv]")
    graph = ";".join(filters)
    run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-filter_complex",
            graph,
            "-map",
            "[outv]",
            "-an",
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(silent),
        ]
    )

    probe = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(silent)],
        capture_output=True,
        text=True,
    )
    match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", probe.stderr)
    if not match:
        raise RuntimeError("Could not determine the edited video duration")
    video_seconds = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))

    run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(silent),
            "-i",
            str(narration),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-af",
            "apad",
            "-t",
            f"{video_seconds:.3f}",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    print(f"Finished: {output} ({video_seconds:.1f} seconds)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True, help="Path to the source screen recording")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "demo/output/financial_document_assistant_walkthrough_en.mp4",
    )
    parser.add_argument(
        "--voiceover",
        type=Path,
        default=ROOT / "demo/output/financial_document_assistant_voiceover_en.mp3",
    )
    parser.add_argument("--audio-only", action="store_true")
    args = parser.parse_args()
    silent = args.output.with_name(args.output.stem + "_silent.mp4")
    if args.voiceover.exists():
        raise FileExistsError(f"Refusing to overwrite existing audio: {args.voiceover}")
    args.voiceover.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(render_voice(args.voiceover))
    if args.audio_only:
        print(f"English narration: {args.voiceover}")
        return
    build_video(args.input, args.voiceover, args.output, silent)
    silent.unlink()
    print(f"English narration: {args.voiceover}")


if __name__ == "__main__":
    main()
