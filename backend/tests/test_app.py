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
    assert payload["version"] == "0.5.48"
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


def test_benchmark_payload_contains_gate_snapshot() -> None:
    from app.api.routes import _benchmark_payload
    from app.models.all_models import CountingBenchmark

    row = CountingBenchmark(
        id=9,
        camera_id=1,
        session_id=8,
        name="Benchmark Session #8",
        source_url="/data/videos/demo.mp4",
        source_fps=25.0,
        source_duration_seconds=60.0,
        line_x1=0.31, line_y1=0.81,
        line_x2=0.84, line_y2=0.55,
        road_x1=0.20, road_y1=0.16,
        road_x2=0.80, road_y2=0.16,
        road_x3=0.96, road_y3=0.98,
        road_x4=0.04, road_y4=0.98,
        tolerance_seconds=0.75,
    )
    payload = _benchmark_payload(row, 3)
    assert payload["geometry"]["line_x1"] == 0.31
    assert payload["geometry"]["line_y2"] == 0.55
    assert payload["geometry"]["road_x4"] == 0.04
    assert payload["mark_count"] == 3


def test_benchmark_clone_compatibility_same_video_same_line() -> None:
    from app.api.routes import _benchmark_clone_compatibility
    from app.models.all_models import CountingBenchmark

    common = dict(
        camera_id=1, name="B", source_url="/data/videos/clip1.mp4",
        line_x1=0.31, line_y1=0.81, line_x2=0.84, line_y2=0.55,
        road_x1=0.20, road_y1=0.16, road_x2=0.80, road_y2=0.16,
        road_x3=0.96, road_y3=0.98, road_x4=0.04, road_y4=0.98,
        tolerance_seconds=0.75,
    )
    source = CountingBenchmark(id=1, session_id=119, **common)
    target = CountingBenchmark(id=2, session_id=120, **common)
    ok, reason = _benchmark_clone_compatibility(source, target)
    assert ok is True
    assert reason == "ok"


def test_benchmark_clone_compatibility_rejects_different_line() -> None:
    from app.api.routes import _benchmark_clone_compatibility
    from app.models.all_models import CountingBenchmark

    source = CountingBenchmark(
        id=1, camera_id=1, session_id=119, name="B1", source_url="/data/videos/clip1.mp4",
        line_x1=0.31, line_y1=0.81, line_x2=0.84, line_y2=0.55,
        road_x1=0.20, road_y1=0.16, road_x2=0.80, road_y2=0.16,
        road_x3=0.96, road_y3=0.98, road_x4=0.04, road_y4=0.98, tolerance_seconds=0.75,
    )
    target = CountingBenchmark(
        id=2, camera_id=1, session_id=120, name="B2", source_url="/data/videos/clip1.mp4",
        line_x1=0.40, line_y1=0.81, line_x2=0.84, line_y2=0.55,
        road_x1=0.20, road_y1=0.16, road_x2=0.80, road_y2=0.16,
        road_x3=0.96, road_y3=0.98, road_x4=0.04, road_y4=0.98, tolerance_seconds=0.75,
    )
    ok, reason = _benchmark_clone_compatibility(source, target)
    assert ok is False
    assert "vạch đếm" in reason


def test_backend_version_metadata() -> None:
    assert app.version == "0.5.48"


def test_v0531_startup_crossing_signature_guard_is_narrow() -> None:
    from app.api.routes import _startup_crossing_signature_duplicate
    assert _startup_crossing_signature_duplicate(0.36, 0.16, 0.012) is True
    assert _startup_crossing_signature_duplicate(0.36, 0.16, 0.080) is False
    assert _startup_crossing_signature_duplicate(1.20, 0.90, 0.010) is False
    assert _startup_crossing_signature_duplicate(0.95, 0.10, 0.010) is False


def test_v0533_ground_truth_mark_update_schema() -> None:
    from app.api.routes import GroundTruthMarkUpdate
    from app.models.all_models import VehicleType

    payload = GroundTruthMarkUpdate(vehicle_type=VehicleType.motorcycle)
    assert payload.vehicle_type == VehicleType.motorcycle
    assert payload.direction is None


def test_v0533_version() -> None:
    assert app.version == "0.5.48"


def test_v0533_ground_truth_mark_update_keeps_timecode() -> None:
    from app.api.routes import GroundTruthMarkUpdate, update_ground_truth_mark
    from app.models.all_models import Direction, GroundTruthCrossing, VehicleType

    mark = GroundTruthCrossing(
        id=77, benchmark_id=12, source_time_seconds=639.119, source_frame_index=15979,
        vehicle_type="bicycle", direction="out", note=None,
    )

    class FakeDb:
        def get(self, model, row_id):
            assert model is GroundTruthCrossing
            return mark if row_id == 77 else None
        def commit(self):
            pass
        def refresh(self, row):
            assert row is mark

    payload = GroundTruthMarkUpdate(vehicle_type=VehicleType.motorcycle, direction=Direction.out)
    result = update_ground_truth_mark(12, 77, payload, FakeDb())
    assert result["vehicle_type"] == "motorcycle"
    assert result["direction"] == "out"
    assert result["source_time_seconds"] == 639.119
    assert mark.source_frame_index == 15979


def test_v0535_two_wheel_rescue_signature_is_narrow() -> None:
    from app.api.routes import _two_wheel_rescue_signature_duplicate
    assert _two_wheel_rescue_signature_duplicate(0.48, 0.012, "rescued", "direct") is True
    assert _two_wheel_rescue_signature_duplicate(0.48, 0.030, "rescued", "direct") is False
    assert _two_wheel_rescue_signature_duplicate(0.30, 0.012, "direct", "direct") is False
    assert _two_wheel_rescue_signature_duplicate(0.75, 0.010, "rescued", "direct") is False


def test_v0537_two_wheel_spatial_signature_extends_only_secondary_methods() -> None:
    from app.api.routes import _two_wheel_spatial_signature_duplicate
    # Longer rescue tail is accepted only with an almost identical crossing point.
    assert _two_wheel_spatial_signature_duplicate(0.70, 0.010, "rescued", "direct") is True
    assert _two_wheel_spatial_signature_duplicate(0.70, 0.020, "rescued", "direct") is False
    # Direct + interpolated may use a small extension; direct/direct never does.
    assert _two_wheel_spatial_signature_duplicate(0.45, 0.008, "interpolated", "direct") is True
    assert _two_wheel_spatial_signature_duplicate(0.30, 0.008, "direct", "direct") is False


def test_v0538_two_wheel_ultra_spatial_signature_extends_only_ultra_close_secondary_tail() -> None:
    from app.api.routes import (
        _two_wheel_spatial_signature_duplicate,
        _two_wheel_ultra_spatial_signature_duplicate,
    )

    # This pair is intentionally beyond V0.5.37 but inside the V0.5.43 ultra tail.
    assert _two_wheel_spatial_signature_duplicate(0.90, 0.006, "rescued", "direct") is False
    assert _two_wheel_ultra_spatial_signature_duplicate(0.90, 0.006, "rescued", "direct") is True
    # Time may be wider only when space is extremely tight.
    assert _two_wheel_ultra_spatial_signature_duplicate(0.90, 0.012, "rescued", "direct") is False
    assert _two_wheel_ultra_spatial_signature_duplicate(0.85, 0.006, "interpolated", "direct") is True
    # Dense direct/direct traffic is never collapsed by this successor rule.
    assert _two_wheel_ultra_spatial_signature_duplicate(0.30, 0.004, "direct", "direct") is False


def test_v0544_same_track_delivery_retry_uses_source_position_not_track_lifetime() -> None:
    from types import SimpleNamespace
    from app.api.routes import _same_track_delivery_retry
    from app.schemas.event import VehicleEventCreate

    existing = SimpleNamespace(
        source_frame_index=100,
        source_time_seconds=4.0,
        detected_at=None,
    )
    retry = VehicleEventCreate(
        camera_id=1, session_id=9, tracking_id=77,
        vehicle_type="motorcycle", direction="in", confidence=0.9,
        source_frame_index=100, source_time_seconds=4.0,
    )
    later_passage = VehicleEventCreate(
        camera_id=1, session_id=9, tracking_id=77,
        vehicle_type="motorcycle", direction="in", confidence=0.9,
        source_frame_index=350, source_time_seconds=14.0,
    )
    assert _same_track_delivery_retry(retry, existing) is True
    assert _same_track_delivery_retry(later_passage, existing) is False


def test_v0544_legacy_same_track_delivery_without_source_coordinates_stays_conservative() -> None:
    from types import SimpleNamespace
    from app.api.routes import _same_track_delivery_retry
    from app.schemas.event import VehicleEventCreate

    existing = SimpleNamespace(source_frame_index=None, source_time_seconds=None, detected_at=None)
    payload = VehicleEventCreate(
        camera_id=1, session_id=9, tracking_id=77,
        vehicle_type="motorcycle", direction="in", confidence=0.9,
    )
    assert _same_track_delivery_retry(payload, existing) is True


def test_v0545_same_track_cycle_guard_closes_only_rapid_same_point_jitter() -> None:
    from types import SimpleNamespace
    from app.api.routes import _same_track_cycle_duplicate_reason
    from app.schemas.event import VehicleEventCreate

    existing = SimpleNamespace(
        source_frame_index=100,
        source_time_seconds=4.0,
        crossing_x=0.50,
        crossing_y=0.50,
        direction="in",
        crossing_method="direct",
    )
    repeat = VehicleEventCreate(
        camera_id=1, session_id=9, tracking_id=77,
        vehicle_type="motorcycle", direction="in", confidence=0.9,
        source_frame_index=170, source_time_seconds=6.8,
        crossing_x=0.505, crossing_y=0.503, crossing_method="rescued",
    )
    later_real_passage = repeat.model_copy(update={
        "source_frame_index": 400, "source_time_seconds": 16.0,
    })
    # V0.5.47: crossing-point jitter must not let an impossible 2.8 s
    # same-direction repeat escape the physical short-cycle closure.
    spatially_distinct_short = repeat.model_copy(update={"crossing_x": 0.60, "crossing_y": 0.60})
    spatially_distinct_late = spatially_distinct_short.model_copy(update={
        "source_frame_index": 400, "source_time_seconds": 16.0,
    })

    assert _same_track_cycle_duplicate_reason(repeat, existing) == "same-track-repeat-jitter"
    assert _same_track_cycle_duplicate_reason(spatially_distinct_short, existing) == "same-track-repeat-jitter"
    assert _same_track_cycle_duplicate_reason(later_real_passage, existing) is None
    assert _same_track_cycle_duplicate_reason(spatially_distinct_late, existing) is None


def test_v0545_same_track_direction_flip_extends_only_with_same_gate_geometry() -> None:
    from types import SimpleNamespace
    from app.api.routes import _same_track_cycle_duplicate_reason
    from app.schemas.event import VehicleEventCreate

    existing = SimpleNamespace(
        source_frame_index=100,
        source_time_seconds=4.0,
        crossing_x=0.50,
        crossing_y=0.50,
        direction="in",
        crossing_method="direct",
    )
    near_flip = VehicleEventCreate(
        camera_id=1, session_id=9, tracking_id=77,
        vehicle_type="motorcycle", direction="out", confidence=0.9,
        source_frame_index=170, source_time_seconds=6.7,
        crossing_x=0.508, crossing_y=0.505, crossing_method="interpolated",
    )
    far_flip = near_flip.model_copy(update={"crossing_x": 0.62, "crossing_y": 0.62})
    late_far_flip = far_flip.model_copy(update={
        "source_frame_index": 210, "source_time_seconds": 8.5,
    })
    assert _same_track_cycle_duplicate_reason(near_flip, existing) == "same-track-direction-flip"
    assert _same_track_cycle_duplicate_reason(far_flip, existing) == "same-track-direction-flip"
    assert _same_track_cycle_duplicate_reason(late_far_flip, existing) is None


def test_v0545_secondary_shadow_signature_closes_only_ultra_close_secondary_tail() -> None:
    from app.api.routes import _secondary_shadow_signature_duplicate

    assert _secondary_shadow_signature_duplicate(0.80, 0.013, "rescued", "direct") is True
    assert _secondary_shadow_signature_duplicate(0.80, 0.020, "rescued", "direct") is False
    assert _secondary_shadow_signature_duplicate(0.70, 0.011, "interpolated", "direct") is True
    assert _secondary_shadow_signature_duplicate(0.30, 0.005, "direct", "direct") is False


def test_v0546_secondary_reverse_shadow_requires_secondary_method_and_ultra_close_point() -> None:
    from app.api.routes import _secondary_reverse_shadow_duplicate

    assert _secondary_reverse_shadow_duplicate(0.60, 0.010, "rescued", "direct") is True
    assert _secondary_reverse_shadow_duplicate(0.50, 0.009, "interpolated", "direct") is True
    assert _secondary_reverse_shadow_duplicate(0.20, 0.004, "direct", "direct") is False
    assert _secondary_reverse_shadow_duplicate(0.80, 0.010, "rescued", "direct") is False
    assert _secondary_reverse_shadow_duplicate(0.50, 0.020, "interpolated", "direct") is False


def test_v0546_same_track_short_cycle_is_physical_not_spatial() -> None:
    from types import SimpleNamespace
    from app.api.routes import _same_track_cycle_duplicate_reason
    from app.schemas.event import VehicleEventCreate

    existing = SimpleNamespace(
        source_frame_index=100, source_time_seconds=4.0,
        crossing_x=0.10, crossing_y=0.50, direction="in", crossing_method="direct",
    )
    impossible_repeat = VehicleEventCreate(
        camera_id=1, session_id=9, tracking_id=77,
        vehicle_type="motorcycle", direction="in", confidence=0.9,
        source_frame_index=195, source_time_seconds=7.8,
        crossing_x=0.88, crossing_y=0.50, crossing_method="direct",
    )
    later_passage = impossible_repeat.model_copy(update={
        "source_frame_index": 350, "source_time_seconds": 14.0,
    })
    assert _same_track_cycle_duplicate_reason(impossible_repeat, existing) == "same-track-repeat-jitter"
    assert _same_track_cycle_duplicate_reason(later_passage, existing) is None


def test_v0548_direct_ultra_shadow_closes_only_tiny_direct_direct_tail() -> None:
    from app.api.routes import _direct_ultra_spatial_shadow_duplicate

    assert _direct_ultra_spatial_shadow_duplicate(0.40, 0.005, "direct", "direct") is True
    assert _direct_ultra_spatial_shadow_duplicate(0.43, 0.005, "direct", "direct") is False
    assert _direct_ultra_spatial_shadow_duplicate(0.35, 0.007, "direct", "direct") is False
    assert _direct_ultra_spatial_shadow_duplicate(0.30, 0.004, "rescued", "direct") is False
