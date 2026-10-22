from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
VIEWPORT = {"width": 1440, "height": 900}


def find_ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    candidates = list((local / "ms-playwright").glob("ffmpeg-*/ffmpeg-win64.exe"))
    if candidates:
        return str(sorted(candidates)[-1])
    raise RuntimeError("FFmpeg not found. Install it with `python -m playwright install ffmpeg`.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Record the live reporting-currency UI")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--token", default=None, help="Demo reviewer token; never commit it")
    parser.add_argument("--skip-export", action="store_true", help="Keep raw WebM only")
    args = parser.parse_args()

    raw_dir = ROOT / "demo" / "raw_recordings"
    output_dir = ROOT / "demo" / "output"
    raw_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    base = args.base_url.rstrip("/")

    raw_path: Path | None = None
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir=str(raw_dir),
            record_video_size=VIEWPORT,
            viewport=VIEWPORT,
            device_scale_factor=1,
        )
        page = context.new_page()
        try:
            page.goto(base, wait_until="domcontentloaded", timeout=30000)
            if page.locator("input[name='token']").count():
                if not args.token:
                    raise RuntimeError("The demo app requires --token; no token was supplied")
                page.locator("input[name='token']").fill(args.token)
                page.locator("form").get_by_role("button").click()
                page.wait_for_load_state("domcontentloaded")

            page.get_by_role("heading", name="A clear view of every expense.").wait_for(
                timeout=20000
            )
            page.evaluate(
                """() => {
                  const label = document.createElement('div');
                  label.textContent = 'DEMO · fictional sample expenses';
                  label.setAttribute('aria-label', 'Demo data: fictional sample expenses');
                  Object.assign(label.style, {
                    position: 'fixed', bottom: '12px', right: '14px', zIndex: '99999',
                    padding: '7px 11px', borderRadius: '999px',
                    background: '#123c35', color: '#fff', font: '600 12px system-ui',
                    boxShadow: '0 2px 10px #0003', pointerEvents: 'none'
                  });
                  document.body.append(label);
                }"""
            )
            page.wait_for_timeout(5000)
            selector = page.locator("#report-currency")
            selector.wait_for()
            if not page.locator("#finance-chart-data").count():
                raise RuntimeError(
                    "Finance dashboard data is missing; refusing to record a simulated view"
                )

            # Show the unified view and let live rate results populate before continuing.
            page.wait_for_function(
                "() => document.querySelector('#rate-date')?.textContent.includes('Rates updated') "
                "|| document.querySelector('#rate-date')?.textContent.includes('Could not load')",
                timeout=15000,
            )
            page.wait_for_timeout(6000)
            for currency in ("EUR", "EGP", "USD"):
                selector.select_option(currency)
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_function(
                    "() => document.querySelector('#report-total')?.textContent "
                    "!== 'Loading rates…'",
                    timeout=15000,
                )
                page.wait_for_timeout(6000)
                if currency == "EGP":
                    page.locator(".exchange-details").scroll_into_view_if_needed()
                    page.wait_for_timeout(7000)
                    page.evaluate("window.scrollTo(0, 0)")
                    page.wait_for_timeout(4000)

            page.get_by_role("link", name="Operations & activity").click()
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(10000)
            page.goto(base, wait_until="domcontentloaded")
            page.wait_for_timeout(30000)
        finally:
            video = page.video
            context.close()
            if video is not None:
                raw_path = Path(video.path())
            browser.close()

    if raw_path is None:
        raise RuntimeError("Playwright did not produce a raw video")
    saved_raw = raw_dir / f"finance_currency_demo_{stamp}.webm"
    raw_path.replace(saved_raw)
    print(f"Raw recording: {saved_raw}")
    if args.skip_export:
        return

    final = output_dir / "finance_agent_demo_silent.mp4"
    if final.exists():
        raise FileExistsError(f"Refusing to overwrite existing video: {final}")
    subprocess.run(
        [
            find_ffmpeg(),
            "-y",
            "-i",
            str(saved_raw),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(final),
        ],
        check=True,
    )
    print(f"MP4: {final}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Recording failed: {exc}", file=sys.stderr)
        sys.exit(1)
