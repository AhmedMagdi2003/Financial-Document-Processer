"""Export the initial PostgreSQL setup from the same tested SQLAlchemy model."""

from pathlib import Path

from sqlalchemy.dialects.postgresql import dialect
from sqlalchemy.schema import CreateIndex, CreateTable

from app.models import Base

if __name__ == "__main__":
    lines = [
        "-- Initial schema; apply once to an empty Supabase project as database owner.",
        "-- Prefer: uv run python -m scripts.setup_db (also seeds categories/projects).",
    ]
    for table in Base.metadata.sorted_tables:
        lines.append(str(CreateTable(table).compile(dialect=dialect())) + ";")
        for index in sorted(table.indexes, key=lambda i: i.name):
            lines.append(str(CreateIndex(index).compile(dialect=dialect())) + ";")
        lines.append(f'ALTER TABLE "{table.name}" ENABLE ROW LEVEL SECURITY;')
    output = Path("supabase/migrations/001_initial.sql")
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = "\n\n".join(lines)
    output.write_text(
        "\n".join(line.rstrip() for line in rendered.splitlines()) + "\n", encoding="utf-8"
    )
    print("Initial PostgreSQL schema exported. No connection or migration executed.")
