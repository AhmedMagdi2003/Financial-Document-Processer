import pytest
from sqlalchemy import create_engine, text

from app.db import initialize


def test_rejection_blocks_publication_until_new_revision(runtime):
    _, _, client = runtime
    item = client.post(
        "/api/v1/content", json={"source": "The fictional team reviewed its protocol."}
    ).json()
    endpoint = f"/api/v1/content/{item['id']}"
    revision = client.get(endpoint).json()["revisions"][0]
    response = client.post(
        endpoint + "/reject",
        json={
            "revision": 1,
            "justification": "The draft needs a clearer explanation before publication.",
        },
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "rejected"
    assert (
        client.post(
            endpoint + "/approve-and-publish", json={"revision": 1, "digest": revision["digest"]}
        ).status_code
        == 409
    )
    assert client.get(endpoint).json()["publications"] == []
    updated = client.put(
        endpoint, json={"revision": 1, "drafts": revision["drafts"], "channels": ["website"]}
    )
    assert updated.json()["decision"] == "draft"
    assert (
        client.post(
            endpoint + "/reject",
            json={"revision": 1, "justification": "This stale revision cannot be rejected."},
        ).status_code
        == 409
    )


def test_reextract_preserves_attempts_and_blocks_recorded_state(runtime):
    _, _, client = runtime
    from tests.conftest import upload_fixture

    doc = upload_fixture(client).json()["document"]
    endpoint = f"/api/v1/documents/{doc['id']}"
    reextracted = client.post(endpoint + "/reextract")
    assert reextracted.status_code == 200
    assert len(client.get(endpoint).json()["attempts"]) == 2
    doc = reextracted.json()
    assert client.post(endpoint + "/confirm", json={"version": doc["version"]}).status_code == 200
    assert client.post(endpoint + "/reextract").status_code == 409


def test_additive_migration_preserves_approved_revision(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    # Simulate the previous schema with an approved revision to verify migration.
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE content_revisions (id TEXT PRIMARY KEY, "
                "content_id TEXT, number INTEGER, drafts JSON, digest TEXT, channels JSON, "
                "approved_by TEXT, approved_at DATETIME)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO content_revisions VALUES "
                "('old:1','old',1,'{}','hash','[]','reviewer','2026-10-21 10:00:00')"
            )
        )
    initialize(engine)
    initialize(engine)
    with engine.connect() as connection:
        row = connection.execute(text("SELECT decision,approved_by FROM content_revisions")).one()
        assert row == ("approved", "reviewer")
    engine.dispose()


def test_currency_and_category_filters(runtime):
    _, _, client = runtime
    from tests.conftest import upload_fixture

    for filename in ["digital.pdf", "receipt.png"]:
        doc = upload_fixture(client, filename).json()["document"]
        assert (
            client.post(
                f"/api/v1/documents/{doc['id']}/confirm", json={"version": doc["version"]}
            ).status_code
            == 200
        )
    assert len(client.get("/api/v1/expenses?currency=EUR").json()) == 1
    assert client.get("/api/v1/expenses/summary?category=travel").json()["totals"] == {
        "USD": "45.5000"
    }
    assert client.get("/api/v1/expenses?project=skills").json() == []
    assert client.get("/api/v1/expenses?start=2026-10-13").json() == []


def test_pending_candidates_are_compared_for_duplicates(runtime):
    _, _, client = runtime
    from tests.conftest import upload_fixture

    first = upload_fixture(client).json()["document"]
    second = upload_fixture(client, "business-duplicate.pdf").json()["document"]
    issues = client.get(f"/api/v1/documents/{second['id']}").json()["issues"]
    duplicate = next(i for i in issues if i["code"] == "POSSIBLE_DUPLICATE")
    assert first["id"] in duplicate["evidence"]["document_ids"]
    assert client.get("/api/v1/expenses").json() == []


@pytest.mark.parametrize("format", ["JPEG", "PNG", "WEBP"])
def test_image_signature_detection(format):
    from io import BytesIO

    from PIL import Image

    from app.inspection import inspect

    out = BytesIO()
    Image.new("RGB", (30, 30), "white").save(out, format)
    result = inspect(out.getvalue(), 100000, 8)
    assert result.mime == Image.MIME[format]
    assert result.route == "vision"
