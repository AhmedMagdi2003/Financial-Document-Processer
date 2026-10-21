# Verification ledger

21 October 2026, Windows, Python 3.12.14, uv 0.12.21.

## Foundation

`uv run ruff check .`: PASS.
`uv run pytest tests/test_foundation.py -q`: **4 passed**.
Commit: `534673b8e9bbce98ab6fc236a9b8e627b3b6954a`.

## Finance and approved publishing increment

`uv run ruff check .`: PASS.
`uv run pytest -q`: **28 passed in 7.06s**.
Tests execute outside the Codex sandbox because Windows asyncio socketpair startup
hangs inside it. Dependency downloads also required network-enabled execution.

Evidence: `tests/test_finance.py`, `tests/test_content.py`, `tests/test_ai.py`.
The content suite contains a real loopback HTTP request test, plus separately named
MockTransport tests for partial failures and idempotency. Provider calls are fakes.
All persistence tests use isolated SQLite, not Supabase. No live cloud result is claimed.

Verified: four finance gates, Decimal semantics, conservative mixed-page routing,
exact file reuse, business duplicate review, legitimate different-item purchases,
amendment history, auth/CSRF, currency-safe summaries, formula-safe CSV, fixed-row
Sheets transport, three distinct offline drafts, edit invalidation, exact revision
approval, partial failure/retry ceiling and authenticated test publisher persistence.

Pending: actual Supabase/private Storage, all three live models, live Google Sheets,
PostgreSQL concurrency, tracing exporters, live AI accuracy evaluation, recording.
Additional manual HTTP/browser evidence will be recorded separately after execution.

## Expanded checks and observed demo

`uv run pytest -q`: **39 passed in 11.35s** after upload boundary, category history,
audit correlation and grounding guards were added. Ruff also passes.
`uv run python -m scripts.evaluate`: **11/11 routing decisions matched** labeled
fixtures; **live inference false**, zero model fields assessed. This is a routing
test, not AI extraction accuracy. Results: `sample_outputs/routing-evaluation.json`.

`uv run python -m scripts.smoke_demo`: PASS against separate Uvicorn servers on
127.0.0.1:8000 and :8011. Produced actual expense CSV, currency summary, three
drafts, publication log and run evidence in `sample_outputs/`. Confirmed EUR 240.00
and USD 45.50; stale revision was refused; three test published pages returned 200.

Browser: signed in locally, inspected finance dashboard, generated three demo
drafts, edited website draft, saved revision 2, clicked Approve & Publish, and
observed all three channels published once with URLs and timestamps. Captures:
`docs/screenshots/finance-2026-10-21.png` and `publication-2026-10-21.png`.
Content ID: `75c1dc2e-a64c-4fa0-82cf-69e3d9dacb36`. See `docs/demo-operator.md`.
No video was recorded; that deliverable remains outstanding.

GitHub remote was empty when checked. Existing credential-manager access passed
`git push --dry-run origin main`; that check did not publish commits. A real push
and remote SHA verification must be recorded separately before claiming submission.
