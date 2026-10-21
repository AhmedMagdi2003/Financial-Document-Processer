# Financial Document Assistant

Independent financial document review and expense tracking workspace. The AI Content
Generation & Publishing Agent is maintained in its own dedicated repository (`Content-Agent`).
Neither application imports or depends on the other.

```text
app/                      # Financial Document Assistant
scripts/, tests/          # Finance setup, demo, evaluation and tests
pyproject.toml, uv.lock   # Finance environment
supabase/migrations/      # Finance-only fresh schema (public)
```

## Run finance independently

Use Python 3.12/3.13 and uv. From the repository root:

```powershell
uv sync --locked
uv run python -m scripts.demo_setup
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open [Finance](http://127.0.0.1:8000), then copy `REVIEWER_TOKEN` from the root
`.env` into the sign-in form. Setup preserves an existing `.env` and does not print
secrets. No content process or publisher is required. The root `.env` and `data/`
are financial runtime configuration.

Demo mode uses known fictional fixture replay, not live AI. Upload
`tests/fixtures/digital.pdf`, `receipt.png`, `missing-total.pdf` or `mixed.pdf`.
Unknown files fail explicitly under the fixture provider.

## Use Financial Operations

Choose the project yourself, upload PDF/JPEG/PNG/WEBP, compare the original with
candidate fields, and use **Edit & revalidate** before **Confirm & record**.
Only confirmed expenses enter the tracker. Duplicate/arithmetic overrides and
dismissals require a justification. Missing total/currency cannot be waived.
Re-extract retains attempts; dismissal preserves history. Categories retain IDs
when edited or deactivated. Filter by project/category/currency/date, inspect
currency-separated summaries, and export CSV. Google Sheets status remains visible
when unconfigured or failed. Operations provides sanitized events and usage/cost.

![Observed finance dashboard before extraction](docs/screenshots/finance-2026-10-21.png)

## Decoupled Content Agent Repository

The Content Generation & Automated Publishing Agent is maintained in a separate repository:
- Located at `D:\Content-Agent` (or its separate GitHub repository).
- Operates its own server on port 8001 and local mock publisher on port 8011.
- Operates its own PostgreSQL schema `content_ops` or dedicated SQLite store.
- Neither application shares code, configuration, or runtime processes.

## Existing data and preserved history

The extraction does not drop old database tables or rewrite Git history. Legacy
content tables/events in an existing combined SQLite database remain intact; the
independent app writes to a separate database. Historical schema upgrade SQL from the combined app
is retained in `supabase/legacy/`; it is not a finance setup migration.

No database dumps, credentials, private planning Markdown/PDF, uploaded originals,
caches or runtime logs are committed. Fictional fixture files and measured sample
exports are included deliberately. Original combined outputs remain in Git history.

## Finance cloud setup

Copy root `.env.example` to `.env`, set `MODE=cloud`, a Supabase
`postgresql+psycopg://...` connection, server-side service key and URL, and distinct
random reviewer/session secrets of at least 24 characters. Use HTTPS and secure
cookies when hosted. Run as a privileged owner in a dedicated test project:

```powershell
uv run python -m scripts.setup_db
```

Setup creates finance tables, stable categories and fictional projects; enables RLS
without public policies; creates/forces a private `originals` bucket. The server
uses a privileged DB connection; browser clients do not query Supabase directly.
`supabase/migrations/001_initial.sql` is a fresh schema export, not an upgrade
runner. Regenerate it with `uv run python -m scripts.export_schema`.
Live Supabase setup and PostgreSQL concurrency are not claimed verified.

## Finance models, rules and integrations

Choose `PROVIDER=gemini|openai|xai` and `MODEL_NAME`, plus its matching key. Existing
LangChain structured-output adapters and bounded LangGraph workflow are retained.
Gemini/OpenAI routes accept text/rendered images; xAI vision is explicitly rejected.
Live credentials/model behavior remain unverified. Fixture mode is explicit demo
only. No silent cross-provider fallback sends private documents elsewhere.

At most three model calls per financial attempt; SDK retries disabled; wrapper
permits one retry per operation within the shared ceiling, 200 ms backoff and
configured timeout. Money is Decimal, decimal strings in JSON and PostgreSQL
NUMERIC(20,4). SQLite is only for small fictional demo/test values.

Four review gates: `MISSING_GRAND_TOTAL`, `MISSING_CURRENCY`, `POSSIBLE_DUPLICATE`,
`TOTAL_INCONSISTENCY`. Zero/missing total or missing currency blocks confirmation.
Arithmetic tolerance is 0.02 currency units, using only explicitly labeled tax and
discount treatment. No missing component is guessed. Refunds/credit notes and
negative components are outside this prototype. Missing optional VAT/number/items
alone never requires review; vendor/date issues are nonblocking provisional warnings.

File SHA-256 uniqueness prevents duplicate submissions. Business checks compare
confirmed expenses and pending candidates, using normalized vendor/number or
vendor/date/amount/currency and explicit items. Confirmation rechecks duplicates,
uses a version compare-and-set, and enforces a unique document-to-expense record.
PDF inspection is conservative for sparse text, images (including inline images),
drawings and annotations; uncertain/mixed PDFs render all pages. No local OCR.
Uploads: 10 MB, eight PDF pages, 25 million image pixels; encrypted/corrupt inputs
are rejected. Originals are private and served only through authenticated routes.

Live calls require configured input/output rates, `PRICING_SOURCE_URL` and
`PRICING_CHECKED_AT`. The cost guard reserves a conservative context/output ceiling;
it is not a provider invoice guarantee. Unknown usage/cost remains unknown.
Optional Langfuse/LangSmith exporters remain unimplemented/unverified;
`TRACING_BACKENDS=none` works and ambient cloud tracing is disabled inside graphs
and model calls. Selecting an unverified exporter blocks live calls explicitly.

For Sheets create an `Expenses` tab with headers
`id,project,category,vendor,date,description,total,currency`. Configure
`SHEETS_SPREADSHEET_ID` and an OAuth access token with Sheets scope/edit access.
Confirmation attempts sync once; retry `POST /api/v1/expenses/{id}/sync` up to three
attempts. Reserved fixed-row PUT upserts avoid duplicates. Do not manually reorder
projection rows. Token refresh is not implemented. Unconfigured sync stays pending.
Fake transport tests are not proof of a live Sheet. Source records survive failures.

## Finance API, tests and limits

[OpenAPI](http://127.0.0.1:8000/docs) includes schemas. API requests require
`Authorization: Bearer <REVIEWER_TOKEN>`. Reviewer sessions use HttpOnly, SameSite
Strict cookies with CSRF protection. This is a demo/internal reviewer identity,
not an identity provider. Zapier can call the same authenticated multipart upload:

```sh
curl -H "Authorization: Bearer $REVIEWER_TOKEN" \
  -H "Idempotency-Key: example-upload-001" \
  -F "project_id=river" -F "file=@tests/fixtures/digital.pdf" \
  http://127.0.0.1:8000/api/v1/documents
```

Processing is synchronous/bounded; `GET /api/v1/documents/{id}` returns persisted
state. Changed input with a reused idempotency key gets 409. Other endpoints:
reviews, fields PATCH, confirm/dismiss/reextract POST, expenses/summary/CSV, category
PATCH and Sheets sync POST.

```powershell
uv run ruff check .
uv run pytest -q
uv run python -m scripts.smoke_demo
```

Content tests run separately in the `Content-Agent` repository.
See each app's docs for actual results and remaining gaps. Supabase, live models,
Sheets, optional traces and a live AI accuracy benchmark still require verification.
The <=5 minute joint video is not recorded; only verified operator instructions/screenshots are provided.
Free-tier limits, pauses and network failures remain operational constraints.
