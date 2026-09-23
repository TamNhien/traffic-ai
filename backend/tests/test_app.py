from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.schemas.camera import CameraCreate, CameraUpdate


class _FakeSession:
    def execute(self, *_args, **_kwargs):
        return None


def _override_get_db():
    yield _FakeSession()


def test_root_metadata() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Traffic AI"
    assert payload["version"] == "0.5.9"
    assert payload["docs"] == "/docs"
    assert payload["health"] == "/api/health"


def test_camera_pipeline_defaults() -> None:
    camera = CameraCreate(name="Demo", code="CAM-001", source_type="video", source_url="/data/videos/demo.mp4")
    assert camera.confidence_threshold == 0.12
    assert camera.line_y1 == 0.5
    assert camera.line_y2 == 0.5


def test_backend_health_does_not_depend_on_ai(monkeypatch) -> None:
    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("Backend /api/health must not call AI Service")

    monkeypatch.setattr("app.api.routes.httpx.get", _fail_if_called)
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.get("/api/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["database"] == "ok"
        assert "ai" not in payload
        assert "ai_service" not in payload
    finally:
        app.dependency_overrides.clear()


def test_camera_update_can_change_source_and_code() -> None:
    payload = CameraUpdate(code="CAM-DEMO", source_type="video", source_url=" /data/videos/demo.mp4 ")
    assert payload.code == "CAM-DEMO"
    assert payload.source_type.value == "video"
    assert payload.source_url == "/data/videos/demo.mp4"



def test_dataset_slug_is_stable() -> None:
    from app.api.routes import _dataset_slug
    assert _dataset_slug("Traffic Dataset 01") == "traffic-dataset-01"
