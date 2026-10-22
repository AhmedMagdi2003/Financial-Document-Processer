"""Tests verifying the 4 quick fixes:
1. Deleting records from DB and UI (expenses and documents)
2. Failed documents can be re-uploaded and processed, and duplicate detection only checks recorded records
3. Adding and editing categories (taxonomy builder)
4. UI chart data generation
"""

from decimal import Decimal
from pathlib import Path
from sqlalchemy import select
from app.models import Category, Document, Expense


def test_delete_expense_record(runtime):
    _, app, client = runtime
    from tests.conftest import upload_fixture

    # 1. Upload and confirm an expense
    res = upload_fixture(client, "digital.pdf")
    assert res.status_code == 200
    doc = res.json()["document"]
    confirm_res = client.post(f"/api/v1/documents/{doc['id']}/confirm", json={"version": doc["version"]})
    assert confirm_res.status_code == 200
    expense_id = confirm_res.json()["id"]

    # Verify expense exists
    with app.state.sessions() as session:
        assert session.get(Expense, expense_id) is not None

    # 2. Delete the expense
    del_res = client.delete(f"/api/v1/expenses/{expense_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # Verify expense is deleted from DB
    with app.state.sessions() as session:
        assert session.get(Expense, expense_id) is None
        # Document state is reset to READY_TO_RECORD
        updated_doc = session.get(Document, doc["id"])
        assert updated_doc.state == "READY_TO_RECORD"


def test_delete_document_and_cascade(runtime):
    _, app, client = runtime
    from tests.conftest import upload_fixture

    res = upload_fixture(client, "missing-total.pdf")
    doc = res.json()["document"]

    with app.state.sessions() as session:
        assert session.get(Document, doc["id"]) is not None

    del_res = client.delete(f"/api/v1/documents/{doc['id']}")
    assert del_res.status_code == 200

    with app.state.sessions() as session:
        assert session.get(Document, doc["id"]) is None


def test_failed_document_can_be_reuploaded_and_processed(runtime):
    _, app, client = runtime
    pdf_bytes = (Path("tests/fixtures") / "missing-total.pdf").read_bytes()

    # Upload document
    resp = client.post(
        "/api/v1/documents",
        data={"project_id": "river"},
        files={"file": ("missing-total.pdf", pdf_bytes)},
    )
    doc = resp.json()["document"]

    # Simulate document being set to FAILED
    with app.state.sessions() as session:
        d = session.get(Document, doc["id"])
        d.state = "FAILED"
        d.error_code = "SIMULATED_FAILURE"
        session.commit()

    # Upload the exact same file again
    re_resp = client.post(
        "/api/v1/documents",
        data={"project_id": "river"},
        files={"file": ("missing-total.pdf", pdf_bytes)},
    )
    assert re_resp.status_code == 200
    re_data = re_resp.json()
    assert re_data["reused"] is False  # Was re-processed, not blocked as dead duplicate!
    assert re_data["document"]["state"] in {"NEEDS_REVIEW", "READY_TO_RECORD"}


def test_add_and_edit_categories(runtime):
    _, app, client = runtime

    # 1. Add a new category
    new_cat_data = {
        "name": "Cloud Infrastructure",
        "definition": "Cloud servers, databases, and related compute services.",
        "active": True,
    }
    create_res = client.post("/api/v1/categories", json=new_cat_data)
    assert create_res.status_code == 200
    cat = create_res.json()
    assert cat["name"] == "Cloud Infrastructure"
    assert cat["id"] == "cloud_infrastructure"

    # 2. Edit the category
    edit_res = client.patch(
        f"/api/v1/categories/{cat['id']}",
        json={
            "name": "Cloud Infrastructure & SaaS",
            "definition": "Cloud servers, storage, and software subscriptions.",
            "active": True,
        },
    )
    assert edit_res.status_code == 200
    updated_cat = edit_res.json()
    assert updated_cat["name"] == "Cloud Infrastructure & SaaS"

    # 3. Delete category
    del_res = client.delete(f"/api/v1/categories/{cat['id']}")
    assert del_res.status_code == 200
    with app.state.sessions() as session:
        assert session.get(Category, cat["id"]) is None


def test_ui_graphs_page_renders(runtime):
    cfg, _, client = runtime

    # Login to access overview
    login_res = client.post("/login", data={"token": cfg.reviewer_token.get_secret_value()})
    assert login_res.status_code in {200, 303}
    res = client.get("/")
    assert res.status_code == 200
    # Check that chart canvas elements and Chart.js script are present
    assert "chart-timeline" in res.text
    assert "chart-categories" in res.text
    assert "chart-pipeline" in res.text
    assert "chart.umd.min.js" in res.text


def test_hosting_switcher_and_make_blueprint(runtime):
    cfg, _, client = runtime
    from app.config import Settings

    # 1. Test hosting switcher properties
    s_ngrok = Settings(_env_file=None, hosting_provider="ngrok", ngrok_url="https://test.ngrok-free.app")
    assert s_ngrok.active_public_url == "https://test.ngrok-free.app"

    s_render = Settings(_env_file=None, hosting_provider="render", render_url="https://test.onrender.com")
    assert s_render.active_public_url == "https://test.onrender.com"

    # 2. Test make.com blueprint endpoint
    login_res = client.post("/login", data={"token": cfg.reviewer_token.get_secret_value()})
    assert login_res.status_code in {200, 303}

    res = client.get(
        "/api/v1/integrations/scripts/google_drive_to_finance_blueprint.json",
        headers={"Authorization": f"Bearer {cfg.reviewer_token.get_secret_value()}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Google Drive to Financial Document Processor"
    assert len(data["flow"]) == 3

