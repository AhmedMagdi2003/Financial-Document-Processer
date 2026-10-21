"""Create an explicit offline demo environment without overwriting existing configuration."""

import secrets
from pathlib import Path

from app.config import Settings
from app.db import initialize, make_engine
from scripts.generate_fixtures import generate


def setup():
    path = Path(".env")
    if path.exists():
        print("Existing .env preserved. Setup requires a fresh demo directory/configuration.")
        return
    Path("data").mkdir(exist_ok=True)
    path.write_text(
        "MODE=demo\nDATABASE_URL=sqlite:///data/workspace.db\nPROVIDER=fixture\n"
        "SECURE_COOKIES=false\n"
        f"REVIEWER_TOKEN={secrets.token_urlsafe(32)}\n"
        f"SESSION_SECRET={secrets.token_urlsafe(32)}\n"
        f"PUBLISHER_SECRET={secrets.token_urlsafe(32)}\n",
        encoding="utf-8",
    )
    cfg = Settings()
    initialize(make_engine(cfg.database_url.get_secret_value()))
    generate()
    print("Offline demo configured. Open .env locally to copy REVIEWER_TOKEN for sign-in.")
    print("Start app on port 8000 and test publisher on port 8011 (see README).")


if __name__ == "__main__":
    setup()
