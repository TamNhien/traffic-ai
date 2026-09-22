from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["pipeline"] == "yolo-bytetrack-line-crossing"


def test_default_model_is_yolo26n(monkeypatch) -> None:
    monkeypatch.delenv("AI_MODEL_NAME", raising=False)
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["model"] == "yolo26n.pt"
