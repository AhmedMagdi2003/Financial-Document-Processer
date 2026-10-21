"""Real HTTP workflow evidence against separately running app and test publisher."""

import json
from pathlib import Path
from time import perf_counter

import httpx

from app.config import Settings


def run():
    cfg = Settings()
    if cfg.mode != "demo" or cfg.provider != "fixture":
        raise RuntimeError("Smoke demo requires explicit local fixture mode")
    output = Path("sample_outputs")
    output.mkdir(exist_ok=True)
    started = perf_counter()
    with httpx.Client(
        base_url="http://127.0.0.1:8000",
        timeout=90,
        headers={"Authorization": f"Bearer {cfg.reviewer_token.get_secret_value()}"},
    ) as client:
        assert client.get("/health").status_code == 200
        documents = []
        for filename in ("digital.pdf", "receipt.png", "missing-total.pdf"):
            response = client.post(
                "/api/v1/documents",
                data={"project_id": "river"},
                files={"file": (filename, (Path("tests/fixtures") / filename).read_bytes())},
            )
            response.raise_for_status()
            doc = response.json()["document"]
            documents.append(doc)
            if doc["state"] == "RECORDED":
                continue
            endpoint = f"/api/v1/documents/{doc['id']}"
            if filename == "missing-total.pdf":
                assert doc["state"] == "NEEDS_REVIEW"
                blocked = client.post(endpoint + "/confirm", json={"version": doc["version"]})
                assert blocked.status_code == 409
                candidate = doc["candidate"]
                candidate["grand_total"] = "120.00"
                edited = client.patch(
                    endpoint + "/fields", json={"version": doc["version"], "candidate": candidate}
                )
                edited.raise_for_status()
                doc = edited.json()
            confirmed = client.post(
                endpoint + "/confirm",
                json={
                    "version": doc["version"],
                    "justification": "Verified fictional fixture; separate demo purchase.",
                },
            )
            confirmed.raise_for_status()
        duplicate = client.post(
            "/api/v1/documents",
            data={"project_id": "river"},
            files={
                "file": (
                    "business-duplicate.pdf",
                    Path("tests/fixtures/business-duplicate.pdf").read_bytes(),
                )
            },
        )
        duplicate.raise_for_status()
        assert duplicate.json()["document"]["state"] == "NEEDS_REVIEW"
        docs = client.get("/api/v1/reviews").json()
        tracker = client.get("/api/v1/expenses.csv")
        tracker.raise_for_status()
        (output / "expense-tracker.csv").write_text(tracker.text, encoding="utf-8")
        summary = client.get("/api/v1/expenses/summary").json()
        assert summary["totals"] == {"EUR": "240.0000", "USD": "45.5000"}
        (output / "financial-summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        evidence = {
            "mode": "financial fixture replay",
            "ai_inference": False,
            "base_url": "http://127.0.0.1:8000",
            "document_urls": [f"http://127.0.0.1:8000/documents/{d['id']}" for d in documents],
            "review_document_ids": [d["id"] for d in docs],
            "duration_seconds": round(perf_counter() - started, 3),
        }
        (output / "smoke-evidence.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    print("PASS: independent HTTP finance upload, review, confirmation and exports.")
    print("Sample outputs saved under sample_outputs/. No live AI or cloud verification claimed.")


if __name__ == "__main__":
    run()
