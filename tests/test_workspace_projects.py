def login(runtime):
    cfg, app, client = runtime
    client.post("/login", data={"token": cfg.reviewer_token.get_secret_value()})
    return client


def test_project_create_rename_and_select(runtime):
    client = login(runtime)
    response = client.post("/api/v1/projects", json={"id": "water-2026", "name": "Water"})
    assert response.status_code == 201
    assert (
        client.post("/api/v1/projects", json={"id": "water-2026", "name": "Other"}).status_code
        == 409
    )
    assert (
        client.patch("/api/v1/projects/water-2026", json={"name": "Water programme"}).status_code
        == 200
    )
    assert {"id": "water-2026", "name": "Water programme"} in client.get("/api/v1/projects").json()
    page = client.get("/?project=water-2026")
    assert page.status_code == 200
    assert '<option value="water-2026" selected>Water programme</option>' in page.text
    assert client.get("/projects").status_code == 200
    assert client.get("/operations?project=water-2026").status_code == 200
    assert client.get("/operations?project=missing").status_code == 404


def test_project_validation_and_auth(runtime):
    _, _, client = runtime
    for body in ({"id": "../bad", "name": "Bad"}, {"id": "valid", "name": "   "}):
        assert client.post("/api/v1/projects", json=body).status_code == 422
    client.headers.pop("Authorization")
    assert client.get("/api/v1/projects").status_code == 401
    assert client.post("/api/v1/projects", json={"id": "test", "name": "Test"}).status_code == 401


def test_integrations_guide_and_csrf(runtime):
    client = login(runtime)
    assert client.get("/integrations").status_code == 200
    assert "Zapier" in client.get("/api/v1/integrations/guide").text
    assert client.get("/api/v1/integrations/scripts/SheetsWebhook.gs").status_code == 200
    assert client.get("/api/v1/integrations/scripts/secret.txt").status_code == 404
    client.headers.pop("Authorization")
    assert client.post("/api/v1/projects", json={"id": "test", "name": "Test"}).status_code == 403
