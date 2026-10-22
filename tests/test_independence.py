from sqlalchemy import inspect


def test_financial_schema_and_authenticated_api(runtime):
    _, app, client = runtime
    assert {"documents", "expenses", "projects"} <= set(
        inspect(app.state.engine).get_table_names()
    )
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/expenses").status_code == 200
