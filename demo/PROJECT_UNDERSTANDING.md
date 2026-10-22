# Financial Document Assistant — Project Understanding

## Scope and entry points

This demo is based on the existing `Financial-Document-Processer` application. The FastAPI entry point is `app.main:app`; the documented local command is:

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The browser dashboard is `/`. Authentication uses the configured reviewer token. Database setup is performed with `uv run python -m scripts.setup_db`.

## Implemented architecture

1. Ingestion accepts PDF, JPEG, PNG, and WEBP files through the dashboard, `POST /api/v1/documents`, and sequential batch processing through `POST /api/v1/batch-upload`.
2. `app.inspection.inspect()` validates file size, file type, PDF integrity, encryption, page count, image dimensions, and routes documents to text, vision, or mixed/fallback inspection.
3. The AI provider in `app.ai` supports OpenAI, Gemini, xAI, and explicit offline fixtures. The configured environment uses OpenAI `gpt-4o-mini`. Structured extraction is validated with the Pydantic `Candidate` schema.
4. `app.financial.process()` runs the inspect → extract → categorize → validate/persist workflow using LangGraph. Candidate values include vendor, date, document number, totals, tax, discount, currency, evidence, and line items.
5. Deterministic validation checks required totals/currency, arithmetic consistency, duplicates, vendor/date quality, category ambiguity, and document-level review conditions.
6. Valid candidates can be automatically recorded as authoritative `Expense` rows when `AUTO_RECORD=true`. Documents needing review are held in `NEEDS_REVIEW` and do not enter confirmed totals.
7. Confirmed expenses can be delivered to Google Sheets. Original files are stored through the configured Supabase Storage integration.
8. Google Drive ingestion is implemented outside FastAPI in `scripts/google_apps_script/DriveIngestion.gs`. It polls a configured folder on a time-based trigger, uses a stable idempotency key, uploads through `/api/v1/documents`, and polls document status.
9. Observability is persisted in events, attempts, usage, audit logs, and delivery records. The Operations page exposes processing status, latency, model calls, and delivery outcomes.
10. The finance page has a reporting-currency selector in the global top bar (USD, EUR, EGP). It converts displayed confirmed spend, category totals, timeline, and per-expense amounts while retaining original invoice/database amounts. The exchange-rate detail panel exposes the source-currency breakdown, pair values, provider, and update date. Rates are served by the authenticated `/api/v1/exchange-rates` endpoint using the free, keyless ExchangeRate-API Open Access feed and a short cache; this is reporting conversion, not a change to source records.

## Automatic versus human-controlled behavior

Automatic: Drive detection, upload, file inspection, AI extraction, categorization, validation, duplicate detection, recording of clean documents, and Sheets delivery when integrations are available.

Human-controlled: reviewer authentication, resolving missing totals/currency, resolving duplicates, correcting arithmetic or extracted fields, confirming a reviewed document, dismissing a document, and selecting filters in the dashboard.

The safety boundary is deliberate: `NEEDS_REVIEW` documents are not recorded until a reviewer resolves the issue and confirms them.

## Environment observations

The local `.env` was inspected by variable name and configuration presence only. It declares cloud mode, OpenAI, `gpt-4o-mini`, automatic recording, Supabase database/storage settings, Google credentials, a Sheets webhook, and ngrok hosting. Secret values were not printed or copied into this directory.

## Demo limitations to verify before recording

Google Drive and Google Sheets are external integrations. Their presence in configuration is not treated as proof of successful delivery. The evidence file must record the actual live result, or explicitly mark the integration as unverified. The sample fixture suite can verify local routing and validation behavior, but it must not be presented as a live Google integration.
