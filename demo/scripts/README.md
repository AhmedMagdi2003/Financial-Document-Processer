# Demo recording scripts

The Playwright harness records the isolated finance preview (including its live currency selector and rate panel), adds a visible fictional-data badge, and keeps the original WebM under `demo/raw_recordings/`. Its MP4 export refuses to overwrite an existing deliverable. Do not record the already-signed-in workspace if it contains real financial records.

Create the isolated fictional demo database once, then start the app:

```powershell
$env:MODE = "demo"
$env:DATABASE_URL = "sqlite:///demo/output/currency_demo.sqlite3"
$env:REVIEWER_TOKEN = "local-fictional-demo-reviewer-token-2026"
$env:SESSION_SECRET = "local-fictional-demo-session-secret-2026"
$env:SECURE_COOKIES = "false"
$env:PROVIDER = "fixture"
$env:AUTO_RECORD = "true"
python -m scripts.setup_db
python demo/scripts/seed_currency_demo.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

In another terminal, record the raw WebM and silent intermediate, then render the English voiceover and mux it into `finance_agent_demo.mp4`:

```powershell
python demo/scripts/record_demo.py --base-url http://127.0.0.1:8765 --token "$env:REVIEWER_TOKEN"
python demo/scripts/render_narration.py --voice en-US-AriaNeural
python demo/scripts/mux_narration.py
```

For a currency-only preview dataset, use the separate SQLite demo instance and `seed_currency_demo.py`. That script only accepts `MODE=demo` with a SQLite URL and seeds explicitly fictional, pre-confirmed sample entries; it does not test AI extraction or external integrations. Read `docs/FINANCIAL_DEMO_VIDEO_GUIDE.md` for claims, safety, and verification requirements. The recording script waits for the actual UI and rate request; it never manufactures FX values.

Install the video-only tools with `uv sync --group demo`. The imageio FFmpeg binary encodes the preserved Playwright WebM capture as H.264 MP4.

The voice renderer transmits only the narration text to Microsoft's online TTS service; it does not send app data or financial records.
