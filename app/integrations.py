"""HTTP boundaries. A successful fake transport is never a live cloud verification."""

from pathlib import Path
from urllib.parse import quote

import httpx


class IntegrationError(RuntimeError):
    pass


class Storage:
    def __init__(self, settings):
        self.settings = settings

    def put(self, key, data, mime):
        cfg = self.settings
        if not (cfg.supabase_url and cfg.supabase_service_key.get_secret_value()):
            path = cfg.local_data_dir / "originals" / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return
        response = httpx.post(
            f"{cfg.supabase_url}/storage/v1/object/{cfg.storage_bucket}/{quote(key)}",
            headers={
                "Authorization": f"Bearer {cfg.supabase_service_key.get_secret_value()}",
                "Content-Type": mime,
                "x-upsert": "false",
            },
            content=data,
            timeout=30,
        )
        if response.is_error:
            raise IntegrationError("STORAGE_UPLOAD_FAILED")

    def get(self, key):
        cfg = self.settings
        if not (cfg.supabase_url and cfg.supabase_service_key.get_secret_value()):
            root = (cfg.local_data_dir / "originals").resolve()
            path = (root / key).resolve()
            if not path.is_relative_to(root):
                raise IntegrationError("INVALID_STORAGE_KEY")
            return path.read_bytes()
        response = httpx.get(
            f"{cfg.supabase_url}/storage/v1/object/authenticated/{cfg.storage_bucket}/{quote(key)}",
            headers={"Authorization": f"Bearer {cfg.supabase_service_key.get_secret_value()}"},
            timeout=30,
        )
        if response.is_error:
            raise IntegrationError("STORAGE_READ_FAILED")
        return response.content

    def delete(self, key):
        cfg = self.settings
        if not (cfg.supabase_url and cfg.supabase_service_key.get_secret_value()):
            root = (cfg.local_data_dir / "originals").resolve()
            path = (root / key).resolve()
            if path.is_relative_to(root) and path.exists():
                path.unlink(missing_ok=True)
            return
        try:
            httpx.delete(
                f"{cfg.supabase_url}/storage/v1/object/{cfg.storage_bucket}/{quote(key)}",
                headers={"Authorization": f"Bearer {cfg.supabase_service_key.get_secret_value()}"},
                timeout=15,
            )
        except Exception:
            pass


class Sheets:
    """Fixed reserved row + values.update makes retries an upsert, not append."""

    def __init__(self, settings, transport=None):
        self.settings = settings
        self.transport = transport

    @property
    def configured(self):
        return bool(
            (
                self.settings.sheets_spreadsheet_id
                and self.settings.sheets_access_token.get_secret_value()
            )
            or getattr(self.settings, "sheets_webhook_url", "")
        )

    def sync(self, row, values):
        if not self.configured:
            raise IntegrationError("SHEETS_NOT_CONFIGURED")
        webhook_url = getattr(self.settings, "sheets_webhook_url", "")
        if webhook_url:
            secret = self.settings.sheets_webhook_secret.get_secret_value()
            if len(secret) < 24:
                raise IntegrationError("SHEETS_WEBHOOK_SECRET_REQUIRED")
            if not webhook_url.startswith("https://"):
                raise IntegrationError("SHEETS_WEBHOOK_HTTPS_REQUIRED")
            with httpx.Client(transport=self.transport, timeout=30) as client:
                response = client.post(
                    webhook_url,
                    json={
                        "secret": secret,
                        "row": row,
                        "values": values,
                        "expense": {
                            "id": values[0],
                            "project": values[1],
                            "category": values[2],
                            "vendor": values[3],
                            "date": values[4],
                            "description": values[5],
                            "total": values[6],
                            "currency": values[7],
                        },
                    },
                )
                # ContentService returns a one-time GET location. Never forward the
                # secret-bearing POST to arbitrary redirects or sign-in pages.
                if response.status_code in (302, 303):
                    location = response.headers.get("location", "")
                    target = httpx.URL(location)
                    if target.scheme != "https" or target.host != "script.googleusercontent.com":
                        raise IntegrationError("SHEETS_WEBHOOK_INVALID_REDIRECT")
                    response = client.get(location)
            if response.is_error:
                raise IntegrationError(f"SHEETS_WEBHOOK_HTTP_{response.status_code}")
            try:
                ack = response.json()
            except ValueError:
                raise IntegrationError("SHEETS_WEBHOOK_INVALID_RESPONSE") from None
            if not isinstance(ack, dict) or ack.get("status") != "ok" or ack.get("id") != values[0]:
                raise IntegrationError("SHEETS_WEBHOOK_NOT_ACKNOWLEDGED")
            return
        sheet_id = quote(self.settings.sheets_spreadsheet_id, safe="")
        token = self.settings.sheets_access_token.get_secret_value()
        with httpx.Client(transport=self.transport, timeout=15) as client:
            response = client.put(
                f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/Expenses!A{row}:H{row}",
                params={"valueInputOption": "RAW"},
                json={"values": [values]},
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.is_error:
            raise IntegrationError(f"SHEETS_HTTP_{response.status_code}")

    def remove(self, row, expense_id):
        """Clear the spreadsheet entry before its database delivery mapping is removed."""
        if not self.configured:
            return
        webhook_url = getattr(self.settings, "sheets_webhook_url", "")
        if webhook_url:
            secret = self.settings.sheets_webhook_secret.get_secret_value()
            if len(secret) < 24:
                raise IntegrationError("SHEETS_WEBHOOK_SECRET_REQUIRED")
            if not webhook_url.startswith("https://"):
                raise IntegrationError("SHEETS_WEBHOOK_HTTPS_REQUIRED")
            with httpx.Client(transport=self.transport, timeout=30) as client:
                response = client.post(webhook_url, json={
                    "secret": secret, "action": "delete", "id": expense_id,
                })
                if response.status_code in (302, 303):
                    location = response.headers.get("location", "")
                    target = httpx.URL(location)
                    if target.scheme != "https" or target.host != "script.googleusercontent.com":
                        raise IntegrationError("SHEETS_WEBHOOK_INVALID_REDIRECT")
                    response = client.get(location)
            if response.is_error:
                raise IntegrationError(f"SHEETS_WEBHOOK_HTTP_{response.status_code}")
            try:
                ack = response.json()
            except ValueError:
                raise IntegrationError("SHEETS_WEBHOOK_INVALID_RESPONSE") from None
            if (
                not isinstance(ack, dict)
                or ack.get("status") != "ok"
                or ack.get("id") != expense_id
            ):
                raise IntegrationError("SHEETS_WEBHOOK_NOT_ACKNOWLEDGED")
            return

        sheet_id = quote(self.settings.sheets_spreadsheet_id, safe="")
        token = self.settings.sheets_access_token.get_secret_value()
        with httpx.Client(transport=self.transport, timeout=15) as client:
            response = client.post(
                f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/Expenses!A{row}:H{row}:clear",
                json={},
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.is_error:
            raise IntegrationError(f"SHEETS_HTTP_{response.status_code}")


def safe_filename(value):
    return Path(value.replace("\\", "/")).name[:250] or "document"
