import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app import financial
from app.inspection import FileRejected, inspect
from app.models import Document, Expense
from app.schemas import Candidate
from tests.conftest import upload_fixture


def codes(candidate):
    return {issue["code"] for issue in financial.validate(Candidate(**candidate))}


def test_four_gates_and_optional_fields():
    assert {"MISSING_GRAND_TOTAL", "MISSING_CURRENCY"} <= codes({})
    assert codes({"grand_total": "10", "currency": "EUR"}) == {"VENDOR_UNKNOWN", "DATE_UNKNOWN"}
    assert "TOTAL_INCONSISTENCY" not in codes(
        {"grand_total": "120", "currency": "EUR", "subtotal": "100"}
    )
    assert "TOTAL_INCONSISTENCY" in codes(
        {
            "grand_total": "140",
            "subtotal": "100",
            "tax": "20",
            "tax_mode": "exclusive",
            "currency": "EUR",
        }
    )


@pytest.mark.parametrize(
    "values",
    [
        {"subtotal": "100", "tax": "20", "tax_mode": "exclusive", "grand_total": "120"},
        {"subtotal": "120", "tax": "20", "tax_mode": "inclusive", "grand_total": "120"},
        {
            "subtotal": "100",
            "tax": "20",
            "tax_mode": "exclusive",
            "discount": "10",
            "discount_explicit": True,
            "grand_total": "110",
        },
        {"subtotal": "0.10", "tax": "0.20", "tax_mode": "exclusive", "grand_total": "0.30"},
    ],
)
def test_decimal_tax_discount(values):
    assert "TOTAL_INCONSISTENCY" not in codes(values)


def test_money_contract_refunds_and_currency():
    for value in [1.2, "NaN", "Infinity", "1.00001"]:
        with pytest.raises(ValidationError):
            Candidate(grand_total=value)
    with pytest.raises(ValidationError):
        Candidate(currency="ZZZ")
    with pytest.raises(financial.Conflict):
        financial.validate(Candidate(grand_total="-10", currency="EUR"))


def test_all_fixture_routes():
    manifest = json.loads(Path("tests/fixtures/ground_truth.json").read_text())
    for row in manifest:
        result = inspect((Path("tests/fixtures") / row["file"]).read_bytes(), 10_000_000, 8)
        assert result.route == row["route"], row["file"]
        if row["file"] == "mixed.pdf":
            assert "Grand total" not in result.text
            assert len(result.images) == 2


@pytest.mark.parametrize("data", [b"", b"%PDF-broken", b"<html>invoice</html>"])
def test_invalid_files(data):
    with pytest.raises(FileRejected):
        inspect(data, 1000, 8)


def test_upload_review_confirm_duplicate_and_summary(runtime):
    cfg, app, client = runtime
    response = upload_fixture(client, key="job-1")
    assert response.status_code == 200, response.text
    doc = response.json()["document"]
    assert doc["state"] == "READY_TO_RECORD"
    assert client.get("/api/v1/expenses/summary").json()["totals"] == {}
    assert upload_fixture(client, key="job-1").json()["document"]["id"] == doc["id"]
    assert upload_fixture(client).json()["reused"]
    assert upload_fixture(client, "receipt.png", "job-1").status_code == 409
    result = client.post(f"/api/v1/documents/{doc['id']}/confirm", json={"version": doc["version"]})
    assert result.status_code == 200, result.text
    assert isinstance(result.json()["total"], str)
    assert Decimal(result.json()["total"]) == Decimal("120.00")
    assert (
        client.post(
            f"/api/v1/documents/{doc['id']}/confirm", json={"version": doc["version"]}
        ).status_code
        == 409
    )
    duplicate = upload_fixture(client, "business-duplicate.pdf").json()["document"]
    assert duplicate["state"] == "NEEDS_REVIEW"
    assert (
        client.post(
            f"/api/v1/documents/{duplicate['id']}/confirm", json={"version": duplicate["version"]}
        ).status_code
        == 409
    )
    legitimate = upload_fixture(client, "legitimate-purchase.pdf").json()["document"]
    assert legitimate["state"] == "READY_TO_RECORD"
    receipt = upload_fixture(client, "receipt.png").json()["document"]
    assert (
        client.post(
            f"/api/v1/documents/{receipt['id']}/confirm", json={"version": receipt["version"]}
        ).status_code
        == 200
    )
    totals = client.get("/api/v1/expenses/summary").json()
    assert totals["totals"] == {"USD": "45.5000", "EUR": "120.0000"}
    assert "120.0000,EUR" in client.get("/api/v1/expenses.csv").text
    with app.state.sessions() as session:
        assert len(session.scalars(select(Expense)).all()) == 2
        assert session.get(Document, duplicate["id"]).state == "NEEDS_REVIEW"


def test_hard_blocker_edit_and_stale_version(runtime):
    _, _, client = runtime
    doc = upload_fixture(client, "missing-total.pdf").json()["document"]
    assert doc["state"] == "NEEDS_REVIEW"
    endpoint = f"/api/v1/documents/{doc['id']}"
    assert (
        client.post(
            endpoint + "/confirm",
            json={"version": doc["version"], "justification": "Override is not permitted"},
        ).status_code
        == 409
    )
    candidate = doc["candidate"]
    candidate["grand_total"] = "120.00"
    result = client.patch(
        endpoint + "/fields", json={"version": doc["version"], "candidate": candidate}
    )
    assert result.status_code == 200, result.text
    assert result.json()["state"] == "READY_TO_RECORD"
    assert (
        client.patch(
            endpoint + "/fields", json={"version": doc["version"], "candidate": candidate}
        ).status_code
        == 409
    )
    assert (
        client.post(endpoint + "/confirm", json={"version": result.json()["version"]}).status_code
        == 200
    )
    history = client.get(endpoint).json()
    assert len(history["attempts"]) == 2
    assert any(issue["resolution"] for issue in history["issues"])


def test_api_auth_and_csrf(runtime):
    cfg, _, client = runtime
    del client.headers["Authorization"]
    assert client.get("/api/v1/expenses").status_code == 401
    assert client.post("/login", data={"token": "wrong"}).status_code == 401
    result = client.post("/login", data={"token": cfg.reviewer_token.get_secret_value()})
    assert result.status_code == 200
    assert (
        client.patch(
            "/api/v1/categories/equipment",
            json={"name": "Equipment", "definition": "Equipment for research", "active": True},
        ).status_code
        == 403
    )
    assert "Financial Operations" in client.get("/").text
    for page in ["/review", "/operations", "/categories"]:
        assert client.get(page).status_code == 200


def test_sheets_upsert_fake_transport(runtime):
    cfg, app, client = runtime
    doc = upload_fixture(client).json()["document"]
    expense = client.post(
        f"/api/v1/documents/{doc['id']}/confirm", json={"version": doc["version"]}
    ).json()
    configured = cfg.model_copy(
        update={
            "sheets_spreadsheet_id": "fake-sheet",
            "sheets_access_token": __import__("pydantic").SecretStr("fake"),
        }
    )
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"updatedRows": 1})

    with app.state.sessions() as session:
        for _ in range(2):
            delivery = financial.sync_sheets(
                session, configured, expense["id"], httpx.MockTransport(handler)
            )
            assert delivery.status == "succeeded"
    assert len(requests) == 1
    assert "Expenses!A2:H2" in str(requests[0].url)


def test_unknown_fixture_fails_without_fake_result(runtime):
    cfg, app, client = runtime
    import pymupdf

    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((30, 40), "An unknown document with some text. Grand total EUR 99.00")
    response = client.post(
        "/api/v1/documents",
        data={"project_id": "river"},
        files={"file": ("unknown.pdf", pdf.tobytes())},
    )
    assert response.json()["document"]["state"] == "FAILED"


def test_summary_is_exact_and_formula_export_is_safe():
    records = [
        Expense(
            id="a",
            document_id="x",
            project_id="river",
            vendor="=CMD()",
            description="@attack",
            vendor_normalized="cmd",
            total=Decimal("0.1"),
            currency="EUR",
            date="2026-10-12",
        ),
        Expense(
            id="b",
            document_id="y",
            project_id="river",
            description="",
            vendor_normalized="",
            total=Decimal("0.2"),
            currency="EUR",
        ),
    ]
    assert financial.summary(records)["totals"] == {"EUR": "0.3"}
    exported = financial.csv_export(records)
    assert "'=CMD()" in exported and "'@attack" in exported
