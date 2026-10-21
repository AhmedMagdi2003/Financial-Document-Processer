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
        if cfg.mode == "demo":
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
        if cfg.mode == "demo":
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


class Sheets:
    """Fixed reserved row + values.update makes retries an upsert, not append."""

    def __init__(self, settings, transport=None):
        self.settings = settings
        self.transport = transport

    @property
    def configured(self):
        return bool(
            self.settings.sheets_spreadsheet_id
            and self.settings.sheets_access_token.get_secret_value()
        )

    def sync(self, row, values):
        if not self.configured:
            raise IntegrationError("SHEETS_NOT_CONFIGURED")
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


def safe_filename(value):
    return Path(value.replace("\\", "/")).name[:250] or "document"
