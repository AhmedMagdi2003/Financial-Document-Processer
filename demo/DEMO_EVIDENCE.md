# Demo Evidence

Status: currency-reporting preview recorded and exported. Full document-ingestion and external-integration demo remains pending.

## Evidence policy

Documentation and configuration alone do not prove execution. The rows below describe only the captured local preview.

| Scenario | Actual result | Verification source | Video timestamp | Status |
|---|---|---|---|---|
| Isolated local demo health | `ok`, configured | `/health` and recorded dashboard load on local demo server | 00:00 | Pass |
| Dashboard currency summary | Total rendered from three seeded fictional USD/EUR/EGP expenses | Isolated SQLite demo DB and finance dashboard | 00:10–00:20 | Pass |
| Reporting-currency conversion | Selector changed across USD, EUR, and EGP; converted total and per-expense values changed; combined category/month totals and live FX details rendered | Playwright recording and rendered exchange-rate response | 00:16–00:50 | Pass |
| Exchange-rate details | USD/EGP `54.385184`; EUR/EGP `61.086906`; provider timestamp `Thu, 22 Oct 2026 00:02:31 +0000` | Captured app panel; ExchangeRate-API Open Access | 00:27–00:45 | Pass |
| OpenAI extraction | Not executed in this currency preview | No live document processing performed | — | Not in scope |
| Image receipt / three-page PDF | Not executed in this currency preview | No document uploads performed | — | Not in scope |
| Automatic recording / human review | Not executed in this currency preview | Seeded expenses are explicitly fictional; no workflow outcome claimed | — | Not in scope |
| Google Drive / Google Sheets | Not executed in this currency preview | No external services connected | — | Not in scope |

## Deliverables

- Final MP4: `demo/output/finance_agent_demo.mp4` (84 seconds, 1440×900, English (US) narration, visible fictional-data badge).
- Original 91-second Playwright capture retained in `demo/raw_recordings/`; the final edit is trimmed to 84 seconds and muxed with narration.
- The isolated SQLite demo database and seed script use fictional-only records.
- English narration is rendered from the script and muxed into the final MP4.

## Limitations

- This is a currency-feature preview, not the full automation demo. It does not verify image/PDF extraction, OpenAI model behavior, exception resolution, Drive ingestion, or Sheets delivery.
- The actual exchange-rate provider response was visible in the captured run. Rates and timestamps change; the values above describe only this recording.
- Raw capture is preserved separately from the MP4.
