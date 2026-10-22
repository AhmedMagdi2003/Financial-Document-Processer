from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000"
VIEWPORT = {"width": 1440, "height": 900}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--token", default=None, help="Reviewer token; omitted uses existing session"
    )
    args = parser.parse_args()

    output = Path(__file__).parents[1] / "raw_recordings"
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(
            record_video_dir=str(output),
            record_video_size=VIEWPORT,
            viewport=VIEWPORT,
        )
        page = context.new_page()

        base = args.base_url.rstrip("/")
        if args.token:
            page.goto(f"{base}/?auth_token={args.token}")
        else:
            page.goto(base)

        page.wait_for_timeout(2000)
        page.click("a[href='/operations']")
        page.wait_for_timeout(2000)
        page.click("a[href='/categories']")
        page.wait_for_timeout(2000)

        context.close()
        browser.close()


if __name__ == "__main__":
    sys.exit(main())
