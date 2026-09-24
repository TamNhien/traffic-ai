from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["pipeline"] == "yolo26s-bytetrack-full-detect-road-count-v5.14"
    assert payload["version"] == "0.5.14"
    assert "runtime" in payload


def test_default_model_is_yolo26s(monkeypatch) -> None:
    monkeypatch.delenv("AI_MODEL_NAME", raising=False)
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["model"] == "yolo26s.pt"
