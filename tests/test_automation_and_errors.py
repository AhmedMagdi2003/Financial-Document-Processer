from decimal import Decimal
from pathlib import Path

import httpx

from app.errors import HumanError, map_error
from app.financial import sync_sheets
from app.models import Expense


def test_error_mapping_structure():
    """Verify that every error code maps to a clear, actionable HumanError."""
    critical_codes = [
        "MODEL_CALL_FAILED",
        "MISSING_GRAND_TOTAL",
        "MISSING_CURRENCY",
        "TOTAL_INCONSISTENCY",
        "ARITHMETIC_MISMATCH",
        "POSSIBLE_DUPLICATE",
        "FILE_REJECTED",
        "CORRUPTED_PDF",
        "STORAGE_UPLOAD_FAILED",
    ]
    for code in critical_codes:
        err = map_error(code)
        assert isinstance(err, HumanError)
        assert len(err.title) > 3
        assert len(err.reason) > 10
        assert len(err.action) > 10
        assert err.category in {
            "ai_extraction",
            "unreadable_document",
            "missing_fields",
            "validation_warning",
            "api_failure",
            "system_error",
        }


def test_exception_mapping_without_sensitive_leaks():
    """Verify raw exceptions are safely mapped without leaking secrets."""
    raw_exc = Exception("google.genai.errors.ClientError: 400 INVALID_ARGUMENT at line 14")
    err = map_error(raw_exc)
    assert "google.genai" not in err.reason
    assert err.can_retry is True


def test_auto_record_valid_document_creates_expense(runtime):
    """Clean documents proceed automatically to RECORDED and create an Expense."""
    cfg, app, client = runtime
    pdf_bytes = (Path("tests/fixtures") / "digital.pdf").read_bytes()
    resp = client.post(
        "/api/v1/documents",
        data={"project_id": "river", "auto_record": "true"},
        files={"file": ("digital.pdf", pdf_bytes)},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["auto_recorded"] is True
    assert data["document"]["state"] == "RECORDED"

    # Verify expense exists and is reflected in financial summary immediately
    summary = client.get("/api/v1/expenses/summary").json()
    assert "EUR" in summary["totals"]
    assert Decimal(summary["totals"]["EUR"]) == Decimal("120.00")


def test_critical_condition_missing_total_stops_auto_record(runtime):
    """Critical condition 1: Missing grand total MUST enter review queue and never auto-record."""
    cfg, app, client = runtime
    pdf_bytes = (Path("tests/fixtures") / "missing-total.pdf").read_bytes()
    resp = client.post(
        "/api/v1/documents",
        data={"project_id": "river", "auto_record": "true"},
        files={"file": ("missing-total.pdf", pdf_bytes)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["auto_recorded"] is False
    assert data["document"]["state"] == "NEEDS_REVIEW"
    issue_codes = [i["code"] for i in data["issues"]]
    assert "MISSING_GRAND_TOTAL" in issue_codes

    # Ensure no expense was created
    summary = client.get("/api/v1/expenses/summary").json()
    assert summary["totals"] == {}


def test_critical_condition_missing_currency_stops_auto_record(runtime):
    """Critical condition 2: Missing currency MUST enter review queue and never auto-record."""
    cfg, app, client = runtime
    pdf_bytes = (Path("tests/fixtures") / "missing-currency.pdf").read_bytes()
    resp = client.post(
        "/api/v1/documents",
        data={"project_id": "river", "auto_record": "true"},
        files={"file": ("missing-currency.pdf", pdf_bytes)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["auto_recorded"] is False
    assert data["document"]["state"] == "NEEDS_REVIEW"
    issue_codes = [i["code"] for i in data["issues"]]
    assert "MISSING_CURRENCY" in issue_codes


def test_critical_condition_arithmetic_inconsistency_stops_auto_record(runtime):
    """Critical condition 4: Arithmetic inconsistency MUST enter review queue."""
    cfg, app, client = runtime
    pdf_bytes = (Path("tests/fixtures") / "arithmetic-conflict.pdf").read_bytes()
    resp = client.post(
        "/api/v1/documents",
        data={"project_id": "river", "auto_record": "true"},
        files={"file": ("arithmetic-conflict.pdf", pdf_bytes)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["auto_recorded"] is False
    assert data["document"]["state"] == "NEEDS_REVIEW"
    issue_codes = [i["code"] for i in data["issues"]]
    assert "TOTAL_INCONSISTENCY" in issue_codes


def test_critical_condition_duplicate_stops_auto_record(runtime):
    """Critical condition 3: Potential duplicate invoice stops auto-record."""
    cfg, app, client = runtime
    # First record the primary document
    pdf_bytes = (Path("tests/fixtures") / "digital.pdf").read_bytes()
    client.post(
        "/api/v1/documents",
        data={"project_id": "river", "auto_record": "true"},
        files={"file": ("digital.pdf", pdf_bytes)},
    )

    # Now upload business duplicate
    dup_bytes = (Path("tests/fixtures") / "business-duplicate.pdf").read_bytes()
    resp = client.post(
        "/api/v1/documents",
        data={"project_id": "river", "auto_record": "true"},
        files={"file": ("business-duplicate.pdf", dup_bytes)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["auto_recorded"] is False
    assert data["document"]["state"] == "NEEDS_REVIEW"
    issue_codes = [i["code"] for i in data["issues"]]
    assert "POSSIBLE_DUPLICATE" in issue_codes


def test_batch_upload_sequential_resilience(runtime):
    """Batch upload processes all files sequentially without one failure stopping others."""
    cfg, app, client = runtime
    f_valid = ("digital.pdf", (Path("tests/fixtures") / "digital.pdf").read_bytes())
    f_missing_cur = (
        "missing-currency.pdf",
        (Path("tests/fixtures") / "missing-currency.pdf").read_bytes(),
    )
    f_discount = ("discount.pdf", (Path("tests/fixtures") / "discount.pdf").read_bytes())

    resp = client.post(
        "/api/v1/batch-upload",
        data={"project_id": "river", "auto_record": "true"},
        files=[
            ("files", f_valid),
            ("files", f_missing_cur),
            ("files", f_discount),
        ],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 3
    assert data["recorded"] == 2  # digital.pdf and discount.pdf
    assert data["review"] == 1    # missing-currency.pdf
    assert data["failed"] == 0

    # Ensure recorded ones are in the summary
    summary = client.get("/api/v1/expenses/summary").json()
    assert "EUR" in summary["totals"]
    assert Decimal(summary["totals"]["EUR"]) == Decimal("230.0000")  # 120 + 110


def test_sheets_webhook_sync(runtime):
    """Google Sheets sync supports webhook dispatch."""
    cfg, app, client = runtime
    cfg.sheets_webhook_url = "https://example.com/webhook"
    from pydantic import SecretStr
    cfg.sheets_webhook_secret = SecretStr("test-secret-at-least-24-characters")

    recorded_payloads = []
    def handler(request: httpx.Request):
        recorded_payloads.append(request.read())
        import json
        val = json.loads(request.read())["values"][0]
        return httpx.Response(200, json={"status": "ok", "id": val})

    transport = httpx.MockTransport(handler)

    # Upload and auto-record with custom mock transport
    pdf_bytes = (Path("tests/fixtures") / "digital.pdf").read_bytes()
    resp = client.post(
        "/api/v1/documents",
        data={"project_id": "river", "auto_record": "true"},
        files={"file": ("digital.pdf", pdf_bytes)},
    )
    doc_id = resp.json()["document"]["id"]

    from sqlalchemy.orm import sessionmaker

    from app.db import make_engine
    session = sessionmaker(bind=make_engine(cfg.database_url.get_secret_value()))()
    expense = session.query(Expense).filter_by(document_id=doc_id).first()
    assert expense is not None

    delivery = sync_sheets(session, cfg, expense.id, transport=transport)
    assert delivery.status == "succeeded"
    assert len(recorded_payloads) == 1
    assert b"Meadow Tools" in recorded_payloads[0]
