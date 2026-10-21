# Impact workspace

A prototype for reviewing project expenses and publishing communications after human
approval. Uses fictional data and test destinations. Implementation is in progress;
no live provider, Supabase, Sheets or social platform has been verified yet.

## Setup

Use Python 3.12 or 3.13 and uv. Copy `.env.example` to `.env`, supply Supabase
Postgres/private Storage settings and distinct random reviewer/session secrets.

```powershell
uv sync
uv run python -m scripts.setup_db
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health: `http://127.0.0.1:8000/health`; API schema: `http://127.0.0.1:8000/docs`.
SQLAlchemy is the single persistence layer; PostgreSQL NUMERIC and transactions
protect money and approval changes. SQLite will be available only in explicit demo
mode and is not a Supabase integration. Original documents use private Storage.

```powershell
uv run ruff check .
uv run pytest
```

The private assessment and implementation guidance are intentionally excluded from
Git. Keep application usage/architecture documentation in this README and `docs/`.
