import ast
from pathlib import Path

from sqlalchemy import inspect


def test_finance_has_no_content_tables_or_routes(runtime):
    _, app, client = runtime
    assert not {"content_items", "content_revisions", "publications"} & set(
        inspect(app.state.engine).get_table_names()
    )
    assert client.get("/content").status_code == 404
    assert (
        client.post("/api/v1/content", json={"source": "Not a finance feature"}).status_code == 404
    )
    for path in Path("app").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("content_app"), path
                assert node.module not in {"app.content", "app.publisher"}, path
