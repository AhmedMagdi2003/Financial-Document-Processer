# Financial Document Assistant

An automated financial operations assistant designed for expense tracking, receipt/invoice inspection, structured extraction, multi-layered deterministic validation, and confirmed record tracking with Supabase PostgreSQL.

---

## Features

- **Document Ingestion**: Accepts PDF, PNG, JPEG, and WEBP formats with MIME validation and page limits.
- **Smart PDF Routing**: Inspects PDF layout with PyMuPDF; routes text-based documents directly and visual/mixed documents through multimodal processing.
- **Deterministic Extraction**: Extracts invoice/receipt number, vendor, dates, line items, taxes, discounts, and currency into typed Pydantic models with `Decimal` precision.
- **Multi-Layer Validation**:
  - `MISSING_GRAND_TOTAL`: Blocks confirmation if no explicit total is detected.
  - `MISSING_CURRENCY`: Blocks confirmation if currency is absent or ambiguous.
  - `POSSIBLE_DUPLICATE`: Flags potential duplicate expenses by comparing SHA-256 hashes, vendor names, dates, amounts, and items.
  - `TOTAL_INCONSISTENCY`: Flags arithmetic discrepancies between subtotal, discounts, taxes, and total.
- **Review Queue**: Dedicated interface for nontechnical operators to review, edit, revalidate, re-extract, confirm, or dismiss flagged candidates.
- **Confirmed Expense Tracker**: Multi-currency spend summaries, date/project/category filters, and CSV export.
- **Authoritative Persistence**: Backed by Supabase PostgreSQL with Row Level Security (RLS) enabled.
- **Outbound Integrations**: Google Sheets sync projection with idempotent row updates.

---

## Quickstart

### Prerequisites
- Python 3.12 or 3.13
- [`uv`](https://docs.astral.sh/uv/) package manager

### 1. Clone & Install Dependencies
```powershell
uv sync --locked
```

### 2. Configure Environment
Copy `.env.example` to `.env` and configure your credentials:
```powershell
Copy-Item .env.example .env
```

### 3. Initialize Database Schema
Run the database setup script to create tables, default fictional projects (`river`, `skills`), and core expense categories:
```powershell
uv run python -m scripts.setup_db
```

### 4. Start the Application
```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.  
Sign in using the `REVIEWER_TOKEN` configured in your `.env` file.

---

## Environment Variables Reference

All application settings are managed in `.env` and typed via Pydantic Settings.

| Variable | Type | Allowed Values / Format | Default | Description |
|---|---|---|---|---|
| `MODE` | string | `cloud`, `demo` | `cloud` | Operational mode. Set to `cloud` for Supabase PostgreSQL. `demo` allows local offline SQLite storage. |
| `DATABASE_URL` | string | `postgresql+psycopg://...` or `sqlite://...` | *Required* | Authoritative database connection string. For Supabase, use the pooled PostgreSQL URL with the `postgresql+psycopg://` driver scheme. |
| `REVIEWER_TOKEN` | string | String (min 24 characters) | *Required* | Secret token used by reviewers to log into the web dashboard and for Bearer token API authorization. |
| `SESSION_SECRET` | string | String (min 24 characters) | *Required* | Secret key used to sign HTTP session cookies. |
| `SECURE_COOKIES` | boolean | `true`, `false` | `false` (local) / `true` (prod) | Whether to enforce `Secure` flag on session cookies (set `true` when hosted behind HTTPS). |
| `LOCAL_DATA_DIR` | path | Directory path | `data` | Local directory for storing temporary files, cache, and uploaded originals when cloud storage is not configured. |
| `SUPABASE_URL` | string | `https://<project-ref>.supabase.co` | Optional | Supabase project URL. Required if using Supabase Storage buckets. |
| `SUPABASE_SERVICE_KEY` | string | Supabase Service Role JWT | Optional | Privileged server-side service key for Supabase Storage uploads. |
| `STORAGE_BUCKET` | string | Bucket name | `originals` | Private Supabase Storage bucket name for original files. |
| `PROVIDER` | string | `none`, `gemini`, `openai`, `xai`, `fixture` | `none` | AI extraction model provider. Select `gemini` for Google GenAI, `openai` for OpenAI, `xai` for Grok, or `none` / `fixture` for offline fixture replay. |
| `MODEL_NAME` | string | Model identifier | e.g. `gemini-2.0-flash` | The specific model name to query (e.g., `gemini-2.0-flash`, `gpt-4o-mini`). |
| `GOOGLE_API_KEY` | string | API key string | Optional | Google AI API key (required if `PROVIDER=gemini`). |
| `OPENAI_API_KEY` | string | API key string | Optional | OpenAI API key (required if `PROVIDER=openai`). |
| `XAI_API_KEY` | string | API key string | Optional | xAI API key (required if `PROVIDER=xai`). |
| `PROVIDER_TIMEOUT` | integer | Seconds | `45` | Timeout in seconds for LLM provider API requests. |
| `MAX_LLM_CALLS` | integer | `1`, `2`, `3` | `3` | Hard ceiling on automated LLM calls per document processing job. |
| `MAX_JOB_COST_USD` | decimal string | Numeric string (e.g. `0.10`) | `0.10` | Hard cost budget per document job. |
| `MAX_INPUT_TOKENS` | integer | Number of tokens | `32000` | Maximum context input tokens permitted per call. |
| `INPUT_USD_PER_MILLION` | decimal string | Rate in USD | e.g. `0.10` | Provider pricing rate per 1M input tokens for internal cost accounting. |
| `OUTPUT_USD_PER_MILLION`| decimal string | Rate in USD | e.g. `0.40` | Provider pricing rate per 1M output tokens for internal cost accounting. |
| `PRICING_SOURCE_URL` | string | URL string | e.g. `https://ai.google.dev/pricing` | Documented source URL for token pricing provenance. |
| `PRICING_CHECKED_AT` | string | Date string (`YYYY-MM-DD`) | e.g. `2026-10-21` | Date when the pricing rates were verified. |
| `SHEETS_SPREADSHEET_ID`| string | Google Spreadsheet ID | Optional | Target Google Spreadsheet ID for outbound expense sync. |
| `SHEETS_ACCESS_TOKEN` | string | OAuth Bearer token | Optional | Access token with Google Sheets edit permissions. |
| `TRACING_BACKENDS` | string | `none`, `langfuse`, `langsmith`, `both` | `none` | External LLM observability export. Keep `none` to use internal database audit feed without cloud tracing. |

---

## API Endpoints

All endpoints under `/api/v1` require `Authorization: Bearer <REVIEWER_TOKEN>`.

- `POST /api/v1/documents`: Upload and inspect a receipt/invoice document (multipart/form-data: `file`, `project_id`, optional `Idempotency-Key` header).
- `GET /api/v1/documents/{id}`: Retrieve document extraction status, candidate fields, and review issues.
- `PATCH /api/v1/documents/{id}/fields`: Correct or update candidate extraction fields before confirmation.
- `POST /api/v1/documents/{id}/confirm`: Confirm and record an expense into the authoritative ledger.
- `POST /api/v1/documents/{id}/dismiss`: Dismiss a rejected or invalid document submission with justification.
- `POST /api/v1/documents/{id}/reextract`: Trigger a new bounded extraction attempt.
- `GET /api/v1/expenses`: Query confirmed expenses with date, project, category, and currency filters.
- `GET /api/v1/expenses/summary`: Currency-separated financial totals and category breakdown.
- `GET /api/v1/expenses/export`: Download confirmed expenses as a CSV file.
- `POST /api/v1/expenses/{id}/sync`: Sync confirmed expense row to Google Sheets.
- `GET /api/v1/categories`: List available expense categories.
- `PATCH /api/v1/categories/{id}`: Edit category definition or active status.
- `GET /health`: Health and configuration check.

---

## Testing & Quality

Run tests:
```powershell
uv run pytest -q
```

Run code formatting and linting:
```powershell
uv run ruff check .
```
