import json
from decimal import Decimal
from pathlib import Path

import httpx
import pymupdf
import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app import financial
from app.financial import Conflict
from app.inspection import FileRejected, inspect
from app.models import Category, Event, Usage
from app.observability import cost_summary
from tests.conftest import upload_fixture


def test_corrupt_encrypted_page_and_size_limits():
    data = Path("tests/fixtures/digital.pdf").read_bytes()
    with pytest.raises(FileRejected, match="size"):
        inspect(data, 10, 8)
    with pytest.raises(FileRejected, match="page"):
        inspect(Path("tests/fixtures/mixed.pdf").read_bytes(), 10000000, 1)
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        encrypted = pdf.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="demo-owner", user_pw="demo-reader"
        )
    with pytest.raises(FileRejected, match="Encrypted"):
        inspect(encrypted, 10000000, 8)


def test_fake_extension_does_not_change_type(runtime):
    _, _, client = runtime
    result = client.post(
        "/api/v1/documents",
        data={"project_id": "river"},
        files={"file": ("invoice.pdf", b"<script>not a pdf</script>", "application/pdf")},
    )
    assert result.status_code == 422
    assert (
        client.post(
            "/api/v1/documents",
            data={"project_id": "hallucinated"},
            files={"file": ("invoice.pdf", Path("tests/fixtures/digital.pdf").read_bytes())},
        ).status_code
        == 409
    )


def test_currency_blocker_and_audited_dismissal(runtime):
    _, app, client = runtime
    doc = upload_fixture(client, "missing-currency.pdf").json()["document"]
    endpoint = f"/api/v1/documents/{doc['id']}"
    assert (
        client.post(
            endpoint + "/confirm",
            json={
                "version": doc["version"],
                "justification": "Cannot waive the currency requirement",
            },
        ).status_code
        == 409
    )
    assert (
        client.post(
            endpoint + "/dismiss",
            json={
                "version": doc["version"],
                "justification": "Duplicate fictional demonstration document.",
            },
        ).status_code
        == 200
    )
    assert client.get(endpoint).json()["document"]["state"] == "DISMISSED"
    assert client.get(endpoint + "/original").content.startswith(b"%PDF-")
    with app.state.sessions() as session:
        assert session.scalar(select(Event).where(Event.operation == "dismiss")).safe_metadata[
            "actor"
        ]


def test_category_edit_keeps_id_and_warns_on_inactive(runtime):
    _, app, client = runtime
    response = client.patch(
        "/api/v1/categories/equipment",
        json={
            "name": "Research equipment",
            "definition": "Physical research instruments and durable hardware",
            "active": False,
        },
    )
    assert response.status_code == 200
    assert response.json()["id"] == "equipment"
    doc = upload_fixture(client).json()["document"]
    assert doc["candidate"]["category_id"] is None
    assert doc["state"] == "READY_TO_RECORD"
    with app.state.sessions() as session:
        assert len(session.scalars(select(Category)).all()) == 6


def test_sheets_failure_has_bounded_retry_and_no_lost_expense(runtime):
    cfg, app, client = runtime
    doc = upload_fixture(client).json()["document"]
    expense = client.post(
        f"/api/v1/documents/{doc['id']}/confirm", json={"version": doc["version"]}
    ).json()
    configured = cfg.model_copy(
        update={"sheets_spreadsheet_id": "fake", "sheets_access_token": SecretStr("fake")}
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(503))
    with app.state.sessions() as session:
        for _ in range(3):
            delivery = financial.sync_sheets(session, configured, expense["id"], transport)
            assert delivery.status == "failed"
        with pytest.raises(Conflict):
            financial.sync_sheets(session, configured, expense["id"], transport)
    assert len(client.get("/api/v1/expenses").json()) == 1


def test_run_request_correlation_and_log_redaction(runtime):
    _, app, client = runtime
    response = upload_fixture(client)
    request_id = response.headers["x-request-id"]
    doc = response.json()["document"]
    with app.state.sessions() as session:
        events = session.scalars(select(Event).where(Event.request_id == request_id)).all()
        assert any(e.run_id and e.resource_id == doc["id"] for e in events)
        assert any(e.stage == "http" and e.safe_metadata["db_queries"] > 0 for e in events)
        for event in events:
            metadata = json.dumps(event.safe_metadata)
            assert "Fictional Meadow Tools" not in metadata
            assert "Sampling kit" not in metadata
            assert "Bearer" not in metadata


def test_partial_cost_is_not_presented_as_complete():
    rows = [
        Usage(
            provider="fake",
            model="x",
            operation="extract",
            run_id="one",
            estimated_usd=Decimal("0.01"),
        ),
        Usage(provider="fake", model="x", operation="categorize", run_id="one"),
    ]
    total = next(g for g in cost_summary(rows) if g["dimension"] == "overall")
    assert total == {
        "dimension": "overall",
        "key": "all",
        "known_estimate_usd": "0.01",
        "unknown_calls": 1,
        "calls": 2,
    }


def test_financial_detail_page(runtime):
    cfg, _, client = runtime
    client.post("/login", data={"token": cfg.reviewer_token.get_secret_value()})
    doc = upload_fixture(client).json()["document"]
    assert "Original document" in client.get(f"/documents/{doc['id']}").text
