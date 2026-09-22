from fastapi.testclient import TestClient

from app.main import app


def test_root_metadata() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Traffic AI"
    assert payload["docs"] == "/docs"
    assert payload["health"] == "/api/health"
