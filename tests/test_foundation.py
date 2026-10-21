import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import initialize, make_engine
from app.main import create_app
from app.models import Category


def test_health():
    with TestClient(create_app()) as client:
        assert client.get("/health").json()["status"] == "ok"


def test_schema_seed_is_repeatable(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    initialize(engine)
    initialize(engine)
    with Session(engine) as session:
        assert len(session.scalars(select(Category)).all()) == 6


def test_fixture_provider_cannot_run_in_cloud():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, mode="cloud", provider="fixture")


def test_requires_runtime_secrets():
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        Settings(_env_file=None).require_runtime()
