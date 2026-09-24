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
    assert payload["version"] == "0.5.15"
    assert payload["docs"] == "/docs"
    assert payload["health"] == "/api/health"


def test_camera_pipeline_defaults() -> None:
    camera = CameraCreate(name="Demo", code="CAM-001", source_type="video", source_url="/data/videos/demo.mp4")
    assert camera.confidence_threshold == 0.06
    assert camera.line_x1 == 0.32
    assert camera.line_y1 == 0.59
    assert camera.line_x2 == 0.84
    assert camera.line_y2 == 0.59
    assert camera.road_x1 == 0.20
    assert camera.road_x3 == 0.96


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


def test_counting_geometry_rejects_gate_outside_road() -> None:
    from app.geometry import validate_counting_geometry
    payload = CameraCreate(name="Demo", code="CAM-GEO", source_type="video", source_url="/data/videos/demo.mp4").model_dump()
    payload.update({"line_x1": 0.02, "line_y1": 0.50, "line_x2": 0.90, "line_y2": 0.50})
    error = validate_counting_geometry(payload)
    assert error is not None
    assert "Hai đầu vạch đếm" in error


def test_counting_geometry_rejects_self_crossing_road_zone() -> None:
    from app.geometry import validate_counting_geometry
    payload = CameraCreate(name="Demo", code="CAM-GEO2", source_type="video", source_url="/data/videos/demo.mp4").model_dump()
    payload.update({
        "road_x1": 0.2, "road_y1": 0.2,
        "road_x2": 0.8, "road_y2": 0.8,
        "road_x3": 0.8, "road_y3": 0.2,
        "road_x4": 0.2, "road_y4": 0.8,
    })
    error = validate_counting_geometry(payload)
    assert error is not None
    assert "bắt chéo" in error
