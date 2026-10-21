"""Run extracted tests from a copy with no financial source or configuration present."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify():
    temporary_root = (ROOT / "tmp").resolve()
    temporary_root.mkdir(exist_ok=True)
    interpreter = ROOT / "content-agent/.venv" / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python")
    with tempfile.TemporaryDirectory(dir=temporary_root, prefix="content-alone-") as directory:
        isolated = Path(directory).resolve()
        if not isolated.is_relative_to(temporary_root):
            raise RuntimeError(
                "Temporary cleanup target is outside the intended workspace tmp directory"
            )
        shutil.copytree(
            ROOT / "content-agent",
            isolated,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(
                ".venv",
                ".env",
                "data",
                "tmp",
                "__pycache__",
                ".pytest_cache",
                ".ruff_cache",
                "*.pyc",
            ),
        )
        code = """import importlib.util, sys
sys.path.insert(0, sys.argv[1])
assert importlib.util.find_spec('app') is None, 'Financial package is visible'
assert importlib.util.find_spec('pymupdf') is None, 'Finance-only dependency leaked'
import pytest
raise SystemExit(pytest.main(['-q', sys.argv[1] + '/tests']))
"""
        result = subprocess.run(
            [str(interpreter), "-I", "-c", code, str(isolated)],
            cwd=isolated,
            check=False,
        )
        if result.returncode:
            raise SystemExit(result.returncode)
    print(
        "PASS: content tests run from an isolated copy without finance source, "
        "settings or PDF dependency."
    )


if __name__ == "__main__":
    verify()
