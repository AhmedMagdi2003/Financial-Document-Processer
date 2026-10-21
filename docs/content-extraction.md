# Content extraction verification

Baseline: main `c8debfd33d1632a777d4542bfdf8ae8973a86c50`, clean working tree,
existing Git identity and origin preserved. `uv run ruff check .` passed;
`uv run pytest -q`: 48 passed in 15.22s on Windows/Python 3.12.

## Boundaries identified before edits

Content-specific: `content.py`, publisher API, content revision/publication models,
content schemas and web routes, templates/JS, content tests and sample outputs.
Shared: provider call wrapper, configuration, SQLAlchemy engine, Event/Usage models,
authentication/session/CSRF, HTTP activity/query timing, common CSS, setup and CI.
The original content workflow also imported `Conflict` from `financial.py`.

## Stage 1: independent extraction

Content code is reused under `content-agent/content_app` with a local errors module,
own environment/lockfile/test suite, isolated `content_ops` PostgreSQL schema (or
separate SQLite demo DB), and a separate session cookie. No finance package import,
runtime request or dependency on finance tables is permitted. Shared small utilities
were copied into each app instead of introducing a new shared framework/package.
The original app remains intact during this additive stage so it remains runnable.
Removal of duplicate root content code and non-destructive legacy data transfer is
the next separately tested cutover stage.

Verified commands (Windows, Python 3.12.14):
- Root `uv run ruff check .`: PASS.
- Root `uv run pytest -q`: **48 passed in 16.37s**.
- Content `uv sync --locked --offline`: PASS in its own `.venv` (83 packages;
  no PDF/image/finance-only dependencies).
- Content `uv run pytest -q`: **19 passed in 5.13s**. This includes the reused
  real loopback HTTP publishing test, revision/rejection/retry checks, provider
  budget/usage tests, schema/cookie/environment isolation and no-finance-import check.
- `content_app` starts via TestClient with no finance configuration.

## Stage 2: complete cutover and isolation

Duplicate content entry points removed from root finance: `app/content.py`, `app/publisher.py`,
content templates, content tests, and content tables in root initial migration.
Legacy revision decisions migration preserved in `supabase/legacy/`.
Content agent received dedicated schema migrations (`content_ops`), read-only legacy
data import tool (`scripts/import_legacy.py`), and independent smoke demo script.

Verified commands (Windows, Python 3.12.14):
- Root `uv run ruff check .`: PASS.
- Root `uv run pytest -q`: **39 passed in 8.86s** (finance-only test suite).
- Content `uv run ruff check .`: PASS.
- Content `uv run pytest -q`: **23 passed in 4.19s** (includes legacy import and web tests).
- `uv run python -m scripts.verify_content_isolation`: PASS (isolated copy executed with no finance code/dependencies).
- Non-destructive legacy data import verified: 4 content items, 7 revisions, 9 publications,
  44 events, and 9 test posts transferred; source databases read-only and hashes unchanged.
- Both smoke demos verified: finance on port 8000, content on port 8001 / publisher on port 8011.

Live provider, Supabase, external tracing and real platform credentials were not
used. The local test publisher and offline model behavior are explicitly labeled.

The four content specifications were found in `Plan/New folder` and read. They are
private guidance and remain excluded from Git. Their requested future features are
review criteria, not authorization to add functionality during this refactor.

Live provider, Supabase, external tracing and real platform credentials were not
used. The local test publisher and offline model behavior are explicitly labeled.

The four content specifications were found in `Plan/New folder` and read. They are
private guidance and remain excluded from Git. Their requested future features are
review criteria, not authorization to add functionality during this refactor.
