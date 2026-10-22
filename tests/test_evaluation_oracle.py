"""Automated test verifying the 19 live benchmark cases against the evaluation oracle."""

import json
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.db import initialize, make_engine
from app.web import create_app


def test_benchmark_suite_100_percent_compliance(tmp_path):
    root_dir = Path(__file__).resolve().parent.parent
    test_dir = root_dir / "financial_agent_test"
    docs_dir = test_dir / "upload_these_documents"

    order = json.load(open(test_dir / "CASE_ORDER.json"))["upload_order"]
    gt_records = json.load(open(test_dir / "GROUND_TRUTH_DO_NOT_UPLOAD.json"))["records"]
    gt_map = {r["file"]: r for r in gt_records}

    eval_db = tmp_path / "eval.db"
    settings = Settings(
        _env_file=None,
        mode="demo",
        provider="fixture",
        database_url=f"sqlite:///{eval_db}",
        local_data_dir=tmp_path / "data",
        reviewer_token="reviewer-" + "x" * 20,
        session_secret="session-" + "x" * 20,
        auto_record=True,
    )
    engine = make_engine(settings.database_url.get_secret_value())
    initialize(engine)
    app = create_app(settings, engine)

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {settings.reviewer_token.get_secret_value()}"

        for filename in order:
            file_path = docs_dir / filename
            gt = gt_map[filename]
            expected_project = gt.get("expected", {}).get("project") or "Civic Data Lab"
            expected_state = gt["initial_state"]
            file_bytes = file_path.read_bytes()

            resp = client.post(
                "/api/v1/documents",
                data={"project_id": expected_project, "auto_record": "true"},
                files={"file": (filename, file_bytes)},
            )

            if filename == "F18_invalid_pdf.pdf":
                assert resp.status_code in {422, 500, 503}
                continue

            assert resp.status_code == 200, resp.text
            data = resp.json()
            doc = data["document"]

            if filename == "F14_exact_duplicate_cloud_subscription.pdf":
                assert data["reused"] is True
            else:
                assert doc["state"] == expected_state, (
                    f"{filename} state {doc['state']} != expected {expected_state}"
                )

        # Verify summary matches oracle
        summary = client.get("/api/v1/expenses/summary").json()
        assert summary["count"] == 12
        assert Decimal(summary["totals"]["USD"]) == Decimal("1185.0000")
        assert Decimal(summary["totals"]["EUR"]) == Decimal("1269.0000")
        assert Decimal(summary["totals"]["EGP"]) == Decimal("2655.0000")
