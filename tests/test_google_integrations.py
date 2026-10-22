import json

import httpx
import pytest

from app.config import Settings
from app.integrations import IntegrationError, Sheets

VALUES = ["expense-1", "river", "equipment", "=EVIL()", "2026-10-22", "test", "12", "EUR"]


def adapter(handler, **kwargs):
    settings = Settings(
        _env_file=None,
        sheets_webhook_url="https://script.google.com/macros/s/test/exec",
        sheets_webhook_secret="a-test-secret-with-24-characters",
        **kwargs,
    )
    return Sheets(settings, httpx.MockTransport(handler))


def test_content_service_redirect_does_not_forward_secret():
    seen = []

    def handler(request):
        seen.append(request)
        if request.method == "POST":
            assert json.loads(request.content)["secret"] == "a-test-secret-with-24-characters"
            return httpx.Response(
                302, headers={"Location": "https://script.googleusercontent.com/macros/echo?k=x"}
            )
        assert request.method == "GET"
        assert request.content == b""
        return httpx.Response(200, json={"status": "ok", "id": VALUES[0]})

    adapter(handler).sync(2, VALUES)
    assert len(seen) == 2


@pytest.mark.parametrize(
    "body", [{"status": "error"}, {"status": "ok"}, [], {"status": "ok", "id": "another-expense"}]
)
def test_webhook_requires_matching_application_ack(body):
    with pytest.raises(IntegrationError, match="NOT_ACKNOWLEDGED"):
        adapter(lambda r: httpx.Response(200, json=body)).sync(2, VALUES)


def test_html_signin_is_failure():
    with pytest.raises(IntegrationError, match="INVALID_RESPONSE"):
        adapter(lambda r: httpx.Response(200, text="<html>Sign in</html>")).sync(2, VALUES)


def test_redirect_to_other_host_rejected():
    with pytest.raises(IntegrationError, match="INVALID_REDIRECT"):
        adapter(lambda r: httpx.Response(302, headers={"Location": "https://example.com"})).sync(
            2, VALUES
        )


def test_secret_required_before_network():
    settings = Settings(_env_file=None, sheets_webhook_url="https://example.com")
    with pytest.raises(IntegrationError, match="SECRET_REQUIRED"):
        Sheets(settings, httpx.MockTransport(lambda r: pytest.fail("unexpected request"))).sync(
            2, VALUES
        )


def test_rest_uses_raw_fixed_row_and_identical_retry():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={})

    settings = Settings(_env_file=None, sheets_spreadsheet_id="test", sheets_access_token="token")
    sheets = Sheets(settings, httpx.MockTransport(handler))
    sheets.sync(2, VALUES)
    sheets.sync(2, VALUES)
    assert requests[0].url == requests[1].url
    assert requests[0].url.params["valueInputOption"] == "RAW"
    assert requests[0].url.path.endswith("Expenses!A2:H2")
    assert json.loads(requests[0].content)["values"][0][3] == "=EVIL()"
