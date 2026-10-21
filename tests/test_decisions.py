import pytest


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
