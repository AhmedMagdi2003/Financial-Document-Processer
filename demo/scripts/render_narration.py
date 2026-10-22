"""Render the demo voiceover in English using Microsoft's online Edge TTS voices."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    "This is a preview of unified currency reporting in the Financial Document Assistant. "
    "The expense entries in this isolated demo workspace are fictional.\n\n"
    "Choose US dollars, euros, or Egyptian pounds from the selector at the top of the application. "
    "The confirmed-spend total updates into the selected reporting currency. "
    "You can switch the reporting view without changing the source records.\n\n"
    "Each expense keeps its original invoice amount alongside its converted reporting value. "
    "Spend from different source currencies is combined in the category and monthly summaries, "
    "making one clear comparison across currencies.\n\n"
    "The details panel shows source-currency totals, the currency pairs, and the provider's update "
    "timestamp. In this capture, the live rates came from ExchangeRate-API Open Access. "
    "The date makes it clear when that rate set was published.\n\n"
    "Currency conversion here is for reporting only. It does not rewrite the source invoice or the "
    "amount stored in the expense record. These sample expenses are fictional, and this short "
    "preview focuses on currency reporting."
)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice", default="en-US-AriaNeural")
    parser.add_argument("--rate", default="-12%")
    args = parser.parse_args()
    output = ROOT / "demo" / "output" / "finance_agent_narration_en.mp3"
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing narration: {output}")
    await edge_tts.Communicate(SCRIPT, args.voice, rate=args.rate).save(str(output))
    print(f"English narration: {output}")


if __name__ == "__main__":
    asyncio.run(main())
