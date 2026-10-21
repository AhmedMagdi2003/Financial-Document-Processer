"""Check staged paths and configured secret values without printing their contents."""

import subprocess
from pathlib import PurePosixPath

from pydantic import SecretStr

from app.config import Settings


def check():
    names = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
    cfg = Settings()
    secrets = [
        getattr(cfg, field).get_secret_value().encode()
        for field in type(cfg).model_fields
        if isinstance(getattr(cfg, field), SecretStr)
        and len(getattr(cfg, field).get_secret_value()) >= 16
        and not (field == "database_url" and cfg.mode == "demo")
    ]
    problems = []
    for name in filter(None, names):
        path = PurePosixPath(name)
        if (
            any(
                part.casefold() in {"plan", "data", "uploads", ".venv", ".uv-cache"}
                for part in path.parts
            )
            or (path.name.startswith(".env") and path.name != ".env.example")
            or path.suffix in {".db", ".sqlite", ".sqlite3", ".key", ".pem"}
        ):
            problems.append(f"Private/runtime path staged: {name}")
        data = subprocess.check_output(["git", "show", f":{name}"])
        if any(value in data for value in secrets):
            problems.append(f"Configured secret value detected in staged file: {name}")
    if problems:
        raise SystemExit("\n".join(problems))
    print(f"PASS: {len(list(filter(None, names)))} staged files; private paths/secrets excluded.")


if __name__ == "__main__":
    check()
