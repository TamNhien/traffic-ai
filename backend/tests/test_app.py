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
    assert payload["version"] == "0.5.67"
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
    assert app.version == "0.5.67"


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
    assert app.version == "0.5.67"


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


def test_v0549_direct_secondary_shadow_is_cross_method_only() -> None:
    from app.api.routes import (
        DIRECT_SECONDARY_SHADOW_LOOKBACK_SECONDS,
        _direct_secondary_shadow_duplicate,
    )

    assert DIRECT_SECONDARY_SHADOW_LOOKBACK_SECONDS == 1.15
    assert _direct_secondary_shadow_duplicate(1.10, 0.0055, "rescued", "direct") is True
    assert _direct_secondary_shadow_duplicate(0.90, 0.0045, "interpolated", "direct") is True
    assert _direct_secondary_shadow_duplicate(0.30, 0.004, "direct", "direct") is False
    assert _direct_secondary_shadow_duplicate(1.16, 0.004, "rescued", "direct") is False
    assert _direct_secondary_shadow_duplicate(0.80, 0.010, "rescued", "direct") is False


def test_v0550_semantic_family_shadow_closes_only_ultra_spatial_class_wobble() -> None:
    from app.api.routes import (
        SEMANTIC_FAMILY_SHADOW_LOOKBACK_SECONDS,
        _semantic_family_shadow_duplicate,
        _direct_secondary_shadow_duplicate,
    )

    assert SEMANTIC_FAMILY_SHADOW_LOOKBACK_SECONDS == 1.20
    assert _semantic_family_shadow_duplicate(
        1.10, 0.009, "rescued", "direct", same_direction=True, same_class=False
    ) is True
    assert _semantic_family_shadow_duplicate(
        0.30, 0.0035, "direct", "direct", same_direction=True, same_class=False
    ) is True
    assert _semantic_family_shadow_duplicate(
        0.30, 0.0035, "direct", "direct", same_direction=True, same_class=True
    ) is False
    assert _semantic_family_shadow_duplicate(
        0.55, 0.0055, "rescued", "direct", same_direction=False, same_class=False
    ) is True
    assert _semantic_family_shadow_duplicate(
        0.55, 0.0055, "direct", "direct", same_direction=False, same_class=False
    ) is False
    assert _semantic_family_shadow_duplicate(
        1.10, 0.012, "rescued", "direct", same_direction=True, same_class=False
    ) is False

    # V0.5.50 also widens only the ultra-spatial tail of the exact-class
    # direct/secondary closure; wider points remain distinct.
    assert _direct_secondary_shadow_duplicate(1.10, 0.0075, "rescued", "direct") is True
    assert _direct_secondary_shadow_duplicate(1.10, 0.0090, "rescued", "direct") is False


def test_v0551_heavy_signature_accepts_real_enum_members_and_string_values() -> None:
    from app.api.routes import _cross_class_heavy_signature_duplicate
    from app.models.all_models import VehicleType

    assert _cross_class_heavy_signature_duplicate(0.70, 0.035, VehicleType.truck, VehicleType.car) is True
    assert _cross_class_heavy_signature_duplicate(0.70, 0.035, "truck", VehicleType.car) is True
    assert _cross_class_heavy_signature_duplicate(0.70, 0.035, VehicleType.truck, VehicleType.truck) is False
    assert _cross_class_heavy_signature_duplicate(0.70, 0.035, VehicleType.bicycle, VehicleType.motorcycle) is False
    assert _cross_class_heavy_signature_duplicate(0.86, 0.035, VehicleType.truck, VehicleType.car) is False
    assert _cross_class_heavy_signature_duplicate(0.70, 0.051, VehicleType.truck, VehicleType.car) is False


def _dedup_event_database():
    """Use the actual endpoint and SQLAlchemy Enum round trips for regressions."""
    from contextlib import contextmanager
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.db.base import Base
    from app.models.all_models import Camera, CountingSession

    @contextmanager
    def database():
        engine = create_engine("sqlite+pysqlite:///:memory:")
        try:
            with engine.connect() as connection:
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            Base.metadata.create_all(engine)
            with Session(engine) as db:
                db.add(Camera(id=1, name="Dedup regression", code="DEDUP-1", source_type="video", source_url="clip.mp4"))
                db.flush()
                db.add(CountingSession(id=1, camera_id=1))
                db.commit()
                yield db
        finally:
            engine.dispose()

    return database()


def _submit_dedup_event(db, **changes):
    from fastapi import Response
    from app.api.routes import internal_event, settings
    from app.schemas.event import VehicleEventCreate

    values = dict(
        camera_id=1, session_id=1, tracking_id=10,
        vehicle_type="motorcycle", direction="in", confidence=0.9,
        source_time_seconds=10.0, source_frame_index=251,
        crossing_x=0.5, crossing_y=0.5, crossing_method="direct",
    )
    values.update(changes)
    response = Response()
    result = internal_event(VehicleEventCreate(**values), response, settings.ai_shared_token, db)
    return result, response


def test_v0551_heavy_enum_signature_deduplicates_without_incrementing_totals() -> None:
    from sqlalchemy import func, select
    from app.models.all_models import CountingSession, VehicleCount, VehicleEvent

    with _dedup_event_database() as db:
        first, _ = _submit_dedup_event(db, vehicle_type="car")
        result, response = _submit_dedup_event(
            db, tracking_id=20, vehicle_type="truck", source_time_seconds=10.70,
            source_frame_index=269, crossing_x=0.535,
        )
        assert result.id == first.id
        assert response.headers["X-TrafficAI-Dedup-Reason"] == "heavy-semantic-signature"
        assert db.scalar(select(func.count()).select_from(VehicleEvent)) == 1
        assert db.get(CountingSession, 1).total_vehicles == 1
        assert db.scalar(select(func.sum(VehicleCount.count))) == 1


def test_v0551_semantic_shadow_finds_later_source_event_already_delivered() -> None:
    from sqlalchemy import func, select
    from app.models.all_models import CountingSession, VehicleEvent

    with _dedup_event_database() as db:
        first, _ = _submit_dedup_event(db, source_time_seconds=11.10, source_frame_index=279)
        result, response = _submit_dedup_event(
            db, tracking_id=20, vehicle_type="bicycle", crossing_method="rescued",
            source_time_seconds=10.0, crossing_x=0.509,
        )
        assert result.id == first.id
        assert response.headers["X-TrafficAI-Dedup-Reason"] == "semantic-family-shadow"
        assert db.scalar(select(func.count()).select_from(VehicleEvent)) == 1
        assert db.get(CountingSession, 1).total_vehicles == 1


def test_v0551_reverse_semantic_shadow_handles_deferred_source_order() -> None:
    with _dedup_event_database() as db:
        first, _ = _submit_dedup_event(db, source_time_seconds=11.0, source_frame_index=276)
        result, response = _submit_dedup_event(
            db, tracking_id=20, vehicle_type="bicycle", direction="out",
            crossing_method="rescued", source_time_seconds=10.45,
            source_frame_index=262, crossing_x=0.5055,
        )
        assert result.id == first.id
        assert response.headers["X-TrafficAI-Dedup-Reason"] == "semantic-family-reverse-shadow"


def test_v0551_candidate_search_has_no_twelve_event_truncation() -> None:
    from app.models.all_models import VehicleEvent

    with _dedup_event_database() as db:
        first, _ = _submit_dedup_event(db, vehicle_type="car")
        # Fourteen newer same-family vehicles remain geometrically distinct
        # from the incoming truck, but used to push its matching car out of
        # the database query's twelve-row limit.
        db.add_all([
            VehicleEvent(
                camera_id=1, session_id=1, tracking_id=100 + index,
                vehicle_type="truck", direction="in", confidence=0.9,
                source_time_seconds=10.30 + index * 0.025,
                crossing_x=0.53, crossing_y=0.53, crossing_method="direct",
            )
            for index in range(14)
        ])
        db.commit()
        result, response = _submit_dedup_event(
            db, tracking_id=20, vehicle_type="truck", source_time_seconds=10.70,
            source_frame_index=269, crossing_x=0.535,
        )
        assert result.id == first.id
        assert response.headers["X-TrafficAI-Dedup-Reason"] == "heavy-semantic-signature"


def test_v0551_symmetric_search_preserves_nearby_vehicles_and_later_passages() -> None:
    from sqlalchemy import func, select
    from app.models.all_models import CountingSession, VehicleEvent

    with _dedup_event_database() as db:
        first, _ = _submit_dedup_event(db, source_time_seconds=11.10, source_frame_index=279)
        adjacent, response = _submit_dedup_event(
            db, tracking_id=20, vehicle_type="bicycle", crossing_method="rescued",
            source_time_seconds=10.0, crossing_x=0.525,
        )
        assert adjacent.id != first.id
        assert response.headers["X-TrafficAI-Deduplicated"] == "0"
        later, response = _submit_dedup_event(db, source_time_seconds=20.0, source_frame_index=501)
        assert later.id not in {first.id, adjacent.id}
        assert response.headers["X-TrafficAI-Deduplicated"] == "0"
        opposite, response = _submit_dedup_event(
            db, tracking_id=30, direction="out", source_time_seconds=20.10,
            source_frame_index=504,
        )
        assert opposite.id != later.id
        assert response.headers["X-TrafficAI-Deduplicated"] == "0"
        assert db.scalar(select(func.count()).select_from(VehicleEvent)) == 4
        assert db.get(CountingSession, 1).total_vehicles == 4


def test_v0551_heavy_signature_preserves_same_class_and_separate_four_wheel_vehicles() -> None:
    from sqlalchemy import func, select
    from app.models.all_models import CountingSession, VehicleEvent

    with _dedup_event_database() as db:
        first, _ = _submit_dedup_event(db, vehicle_type="car")
        adjacent, response = _submit_dedup_event(
            db, tracking_id=20, vehicle_type="car", source_time_seconds=10.70,
            source_frame_index=269, crossing_x=0.535,
        )
        assert adjacent.id != first.id
        assert response.headers["X-TrafficAI-Deduplicated"] == "0"
        truck, response = _submit_dedup_event(
            db, tracking_id=30, vehicle_type="truck", source_time_seconds=10.80,
            source_frame_index=271, crossing_x=0.60,
        )
        assert truck.id not in {first.id, adjacent.id}
        assert response.headers["X-TrafficAI-Deduplicated"] == "0"
        assert db.scalar(select(func.count()).select_from(VehicleEvent)) == 3
        assert db.get(CountingSession, 1).total_vehicles == 3


def test_v0553_delivery_retry_prefers_source_seconds_over_frames_and_wall_clock() -> None:
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from app.api.routes import _same_track_delivery_retry
    from app.schemas.event import VehicleEventCreate

    delivered = datetime(2026, 10, 3, tzinfo=timezone.utc)
    existing = SimpleNamespace(source_time_seconds=4.0, source_frame_index=100, detected_at=delivered)
    later = VehicleEventCreate(
        camera_id=1, session_id=9, tracking_id=77,
        vehicle_type="motorcycle", direction="in", confidence=0.9,
        source_time_seconds=14.0, source_frame_index=102,
        detected_at=delivered + timedelta(seconds=0.1),
    )
    retry = later.model_copy(update={"source_time_seconds": 4.08, "source_frame_index": 400})
    assert _same_track_delivery_retry(later, existing) is False
    assert _same_track_delivery_retry(retry, existing) is True


def test_v0553_delivery_retry_uses_frames_before_delivery_clock_fallback() -> None:
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from app.api.routes import _same_track_delivery_retry
    from app.schemas.event import VehicleEventCreate

    delivered = datetime(2026, 10, 3, tzinfo=timezone.utc)
    existing = SimpleNamespace(source_time_seconds=None, source_frame_index=100, detected_at=delivered)
    later = VehicleEventCreate(
        camera_id=1, session_id=9, tracking_id=77,
        vehicle_type="motorcycle", direction="in", confidence=0.9,
        source_frame_index=400, detected_at=delivered + timedelta(seconds=0.1),
    )
    retry = later.model_copy(update={"source_frame_index": 102, "detected_at": delivered + timedelta(seconds=10)})
    assert _same_track_delivery_retry(later, existing) is False
    assert _same_track_delivery_retry(retry, existing) is True
    legacy = SimpleNamespace(source_time_seconds=None, source_frame_index=None, detected_at=delivered)
    assert _same_track_delivery_retry(later.model_copy(update={"source_frame_index": None}), legacy) is True


def test_v0553_cycle_guard_preserves_low_fps_passages_with_source_seconds() -> None:
    from types import SimpleNamespace
    from app.api.routes import _same_track_cycle_duplicate_reason
    from app.schemas.event import VehicleEventCreate

    existing = SimpleNamespace(
        source_frame_index=100, source_time_seconds=4.0,
        crossing_x=0.5, crossing_y=0.5, direction="in", crossing_method="direct",
    )
    passage = VehicleEventCreate(
        camera_id=1, session_id=9, tracking_id=77,
        vehicle_type="motorcycle", direction="out", confidence=0.9,
        source_frame_index=160, source_time_seconds=10.0,
        crossing_x=0.5, crossing_y=0.5, crossing_method="rescued",
    )
    assert _same_track_cycle_duplicate_reason(passage, existing) is None
    assert _same_track_cycle_duplicate_reason(passage.model_copy(update={"direction": "in"}), existing) is None
    # When the source clock is unavailable, the historical frame guard remains.
    assert _same_track_cycle_duplicate_reason(passage.model_copy(update={"source_time_seconds": None}), existing) == "same-track-direction-flip"


def test_v0553_same_track_neighbor_uses_source_order_not_delivery_id() -> None:
    from types import SimpleNamespace
    from app.api.routes import _same_track_source_neighbor, _same_track_cycle_duplicate_reason
    from app.schemas.event import VehicleEventCreate

    earlier = SimpleNamespace(
        id=1, source_time_seconds=10.0, source_frame_index=251,
        crossing_x=0.5, crossing_y=0.5, direction="in", crossing_method="direct",
    )
    later = SimpleNamespace(
        id=2, source_time_seconds=30.0, source_frame_index=751,
        crossing_x=0.5, crossing_y=0.5, direction="out", crossing_method="direct",
    )
    payload = VehicleEventCreate(
        camera_id=1, session_id=9, tracking_id=77,
        vehicle_type="motorcycle", direction="in", confidence=0.9,
        source_time_seconds=10.4, source_frame_index=751,
        crossing_x=0.5, crossing_y=0.5, crossing_method="direct",
    )
    assert _same_track_source_neighbor(payload, [later, earlier]) is earlier
    assert _same_track_cycle_duplicate_reason(payload, earlier) == "same-track-repeat-jitter"
    assert _same_track_source_neighbor(payload.model_copy(update={"source_time_seconds": None}), [later, earlier]) is later
    assert _same_track_source_neighbor(payload.model_copy(update={"source_time_seconds": None, "source_frame_index": None}), [later, earlier]) is later
    assert _same_track_source_neighbor(payload, []) is None


def test_v0553_late_same_track_retry_preserves_completed_in_out_in_cycle() -> None:
    from sqlalchemy import func, select
    from app.models.all_models import CountingSession, VehicleCount, VehicleEvent

    with _dedup_event_database() as db:
        first, _ = _submit_dedup_event(db)
        reverse, response = _submit_dedup_event(db, direction="out", source_time_seconds=16.0, source_frame_index=401)
        assert response.headers["X-TrafficAI-Deduplicated"] == "0"
        second_in, response = _submit_dedup_event(db, source_time_seconds=22.0, source_frame_index=551)
        assert response.headers["X-TrafficAI-Deduplicated"] == "0"
        retried, response = _submit_dedup_event(db)
        assert retried.id == first.id
        assert response.headers["X-TrafficAI-Dedup-Reason"] == "same-track-delivery-retry"
        assert len({first.id, reverse.id, second_in.id}) == 3
        assert db.scalar(select(func.count()).select_from(VehicleEvent)) == 3
        assert db.get(CountingSession, 1).total_vehicles == 3
        assert db.scalar(select(func.sum(VehicleCount.count))) == 3


def test_v0553_low_fps_cycle_does_not_merge_passages_delivered_together() -> None:
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import func, select
    from app.models.all_models import CountingSession, VehicleEvent

    delivered = datetime(2026, 10, 3, tzinfo=timezone.utc)
    with _dedup_event_database() as db:
        first, _ = _submit_dedup_event(db, source_frame_index=101, detected_at=delivered)
        reverse, response = _submit_dedup_event(
            db, direction="out", source_time_seconds=16.0,
            source_frame_index=161, detected_at=delivered + timedelta(seconds=0.1),
        )
        assert response.headers["X-TrafficAI-Deduplicated"] == "0"
        second_in, response = _submit_dedup_event(
            db, source_time_seconds=22.0, source_frame_index=221,
            detected_at=delivered + timedelta(seconds=0.2),
        )
        assert response.headers["X-TrafficAI-Deduplicated"] == "0"
        assert len({first.id, reverse.id, second_in.id}) == 3
        assert db.scalar(select(func.count()).select_from(VehicleEvent)) == 3
        assert db.get(CountingSession, 1).total_vehicles == 3


def test_v0553_deferred_same_track_jitter_finds_adjacent_source_passage() -> None:
    from sqlalchemy import func, select
    from app.models.all_models import CountingSession, VehicleEvent

    with _dedup_event_database() as db:
        first, _ = _submit_dedup_event(db)
        later, _ = _submit_dedup_event(db, direction="out", source_time_seconds=30.0, source_frame_index=751)
        rejected, response = _submit_dedup_event(db, source_time_seconds=10.4, source_frame_index=261)
        assert rejected.id == first.id
        assert rejected.id != later.id
        assert response.headers["X-TrafficAI-Dedup-Reason"] == "same-track-repeat-jitter"
        assert db.scalar(select(func.count()).select_from(VehicleEvent)) == 2
        assert db.get(CountingSession, 1).total_vehicles == 2


def test_v0554_session_event_requires_owning_camera() -> None:
    from types import SimpleNamespace
    from app.api.routes import _event_session_camera_matches

    session = SimpleNamespace(camera_id=1)
    assert _event_session_camera_matches(session, 1) is True
    assert _event_session_camera_matches(session, 2) is False


def test_v0554_session_late_delivery_refreshes_suppression() -> None:
    from types import SimpleNamespace
    from app.api.routes import _sync_session_persisted_total

    session = SimpleNamespace(total_vehicles=3, worker_total_vehicles=7, dedup_suppressed_events=4)
    _sync_session_persisted_total(session, 4)
    assert session.total_vehicles == 4
    assert session.dedup_suppressed_events == 3


def test_v0554_session_running_totals_do_not_invent_worker_suppression() -> None:
    from types import SimpleNamespace
    from app.api.routes import _sync_session_persisted_total

    session = SimpleNamespace(total_vehicles=3, worker_total_vehicles=None, dedup_suppressed_events=0)
    _sync_session_persisted_total(session, 4)
    assert session.total_vehicles == 4
    assert session.dedup_suppressed_events == 0


def test_v0554_session_delayed_count_never_makes_suppression_negative() -> None:
    from types import SimpleNamespace
    from app.api.routes import _sync_session_persisted_total

    session = SimpleNamespace(total_vehicles=3, worker_total_vehicles=3, dedup_suppressed_events=0)
    _sync_session_persisted_total(session, 4)
    assert session.total_vehicles == 4
    assert session.dedup_suppressed_events == 0


def test_v0554_session_finish_cannot_own_a_newer_replay_camera() -> None:
    from types import SimpleNamespace
    from app.api.routes import _session_finish_owns_camera

    old = SimpleNamespace(id=1)
    latest = SimpleNamespace(id=2)
    assert _session_finish_owns_camera(old, latest) is False
    assert _session_finish_owns_camera(latest, latest) is True
    assert _session_finish_owns_camera(old, None) is True


def test_v0554_session_remote_stop_without_initial_session_cannot_own_new_replay() -> None:
    from types import SimpleNamespace
    from app.api.routes import _session_finish_owns_camera

    assert _session_finish_owns_camera(None, None) is True
    assert _session_finish_owns_camera(None, SimpleNamespace(id=1)) is False


def test_v0554_session_camera_mismatch_is_rejected_before_delivery_retry() -> None:
    import pytest
    from fastapi import HTTPException
    from sqlalchemy import func, select
    from app.models.all_models import CountingSession, VehicleCount, VehicleEvent

    with _dedup_event_database() as db:
        first, _ = _submit_dedup_event(db)
        with pytest.raises(HTTPException) as rejected:
            _submit_dedup_event(db, camera_id=2)
        assert rejected.value.status_code == 422
        assert db.scalar(select(func.count()).select_from(VehicleEvent)) == 1
        assert db.get(CountingSession, 1).total_vehicles == 1
        assert db.scalar(select(func.sum(VehicleCount.count))) == 1
        assert first.camera_id == 1


def test_v0554_session_missing_event_owner_is_rejected_without_writes() -> None:
    import pytest
    from fastapi import HTTPException
    from sqlalchemy import func, select
    from app.models.all_models import CountingSession, VehicleCount, VehicleEvent

    with _dedup_event_database() as db:
        with pytest.raises(HTTPException) as rejected:
            _submit_dedup_event(db, session_id=999)
        assert rejected.value.status_code == 404
        assert db.scalar(select(func.count()).select_from(VehicleEvent)) == 0
        assert db.get(CountingSession, 1).total_vehicles == 0
        assert db.scalar(select(func.count()).select_from(VehicleCount)) == 0


def test_v0554_session_finish_retry_keeps_newer_camera_active_and_first_end_time() -> None:
    from app.api.routes import SessionFinish, internal_session_finish, settings
    from app.models.all_models import Camera, CameraStatus, CountingSession, SessionStatus

    with _dedup_event_database() as db:
        _submit_dedup_event(db)
        internal_session_finish(1, SessionFinish(status="completed", total_vehicles=3), settings.ai_shared_token, db)
        ended_at = db.get(CountingSession, 1).ended_at
        db.add(CountingSession(id=2, camera_id=1, status=SessionStatus.running))
        db.get(Camera, 1).status = CameraStatus.active
        db.commit()

        internal_session_finish(1, SessionFinish(status="error", total_vehicles=3), settings.ai_shared_token, db)
        assert db.get(Camera, 1).status == CameraStatus.active
        assert db.get(CountingSession, 2).status == SessionStatus.running
        assert db.get(CountingSession, 1).ended_at == ended_at


def test_v0554_session_late_old_replay_event_updates_only_its_session_totals() -> None:
    from app.api.routes import SessionFinish, internal_session_finish, settings
    from app.models.all_models import Camera, CameraStatus, CountingSession, SessionStatus

    with _dedup_event_database() as db:
        _submit_dedup_event(db)
        internal_session_finish(1, SessionFinish(status="completed", total_vehicles=3), settings.ai_shared_token, db)
        assert db.get(CountingSession, 1).dedup_suppressed_events == 2
        db.add(CountingSession(id=2, camera_id=1, status=SessionStatus.running))
        db.get(Camera, 1).status = CameraStatus.active
        db.commit()

        late, response = _submit_dedup_event(db, source_time_seconds=20.0, source_frame_index=501)
        assert response.headers["X-TrafficAI-Deduplicated"] == "0"
        assert late.session_id == 1
        assert db.get(CountingSession, 1).total_vehicles == 2
        assert db.get(CountingSession, 1).dedup_suppressed_events == 1
        assert db.get(CountingSession, 2).total_vehicles == 0
        assert db.get(Camera, 1).status == CameraStatus.active


def test_v0554_stale_failed_start_preserves_newer_active_camera(monkeypatch) -> None:
    from types import SimpleNamespace
    import pytest
    from fastapi import HTTPException
    from app.api.routes import start_camera
    from app.models.all_models import Camera, CameraStatus, CountingSession, SessionStatus

    with _dedup_event_database() as db:
        monkeypatch.setattr("app.api.routes.httpx.get", lambda *_args, **_kwargs: SimpleNamespace(is_success=True, json=lambda: {"status": "completed"}))

        def remote_post(url, **_kwargs):
            if url.endswith("/sources/validate"):
                return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"valid": True})
            assert url.endswith("/pipelines/start")
            db.add(CountingSession(id=3, camera_id=1, status=SessionStatus.running))
            db.get(Camera, 1).status = CameraStatus.active
            db.commit()
            raise RuntimeError("Deferred failure for the earlier start request")

        monkeypatch.setattr("app.api.routes.httpx.post", remote_post)
        with pytest.raises(HTTPException) as rejected:
            start_camera(1, db)
        assert rejected.value.status_code == 502
        assert db.get(CountingSession, 2).status == SessionStatus.error
        assert db.get(CountingSession, 3).status == SessionStatus.running
        assert db.get(Camera, 1).status == CameraStatus.active


def test_v0554_stale_stop_preserves_newer_active_camera(monkeypatch) -> None:
    from types import SimpleNamespace
    from app.api.routes import stop_camera
    from app.models.all_models import Camera, CameraStatus, CountingSession, SessionStatus

    with _dedup_event_database() as db:
        db.get(Camera, 1).status = CameraStatus.active
        db.commit()

        def remote_stop(_url, **_kwargs):
            db.add(CountingSession(id=2, camera_id=1, status=SessionStatus.running))
            db.get(Camera, 1).status = CameraStatus.active
            db.commit()
            return SimpleNamespace(status_code=200)

        monkeypatch.setattr("app.api.routes.httpx.post", remote_stop)
        assert stop_camera(1, db)["status"] == "stopped"
        assert db.get(CountingSession, 1).status == SessionStatus.stopped
        assert db.get(CountingSession, 2).status == SessionStatus.running
        assert db.get(Camera, 1).status == CameraStatus.active


def test_v0560_stop_ack_without_json_keeps_legacy_status_only_contract(monkeypatch) -> None:
    from types import SimpleNamespace
    from app.api.routes import stop_camera
    from app.models.all_models import Camera, CameraStatus, CountingSession, SessionStatus

    with _dedup_event_database() as db:
        db.get(Camera, 1).status = CameraStatus.active
        db.commit()

        monkeypatch.setattr(
            "app.api.routes.httpx.post",
            lambda _url, **_kwargs: SimpleNamespace(status_code=200),
        )
        result = stop_camera(1, db)
        assert result == {"status": "stopped", "camera_id": 1}
        assert db.get(CountingSession, 1).status == SessionStatus.stopped
        assert db.get(Camera, 1).status == CameraStatus.inactive


def test_v0560_stop_ack_with_non_object_json_remains_rejected(monkeypatch) -> None:
    import pytest
    from types import SimpleNamespace
    from fastapi import HTTPException
    from app.api.routes import stop_camera

    with _dedup_event_database() as db:
        monkeypatch.setattr(
            "app.api.routes.httpx.post",
            lambda _url, **_kwargs: SimpleNamespace(status_code=200, json=lambda: []),
        )
        with pytest.raises(HTTPException) as rejected:
            stop_camera(1, db)
        assert rejected.value.status_code == 502
        assert "AI stop response must be an object" in str(rejected.value.detail)


def test_v0554_class_trace_targets_use_ai_clock_without_changing_scoring() -> None:
    from types import SimpleNamespace
    from app.api.routes import _benchmark_trace_targets
    from app.benchmarking import match_crossings

    gt = SimpleNamespace(id=1, source_time_seconds=10.0, direction="in", vehicle_type="bicycle")
    event = SimpleNamespace(id=11, source_time_seconds=10.6203, direction="in", vehicle_type="motorcycle", tracking_id=77)
    report = match_crossings([gt], [event], 0.75)
    scores = {key: report[key] for key in ("matched", "missed", "false_positives", "class_accuracy")}
    targets = _benchmark_trace_targets(report, [event])
    assert len(targets) == 1
    assert targets[0][1] == 10.6203
    assert targets[0][0]["time"] == 10.0
    assert targets[0][0]["ai_tracking_id"] == 77
    assert scores == {key: report[key] for key in scores}


def test_v0554_class_trace_missing_event_uses_ai_time_and_known_track() -> None:
    from app.api.routes import _benchmark_trace_targets

    mismatch = {"ai_event_id": 11, "time": 10.0, "ai_time": 10.6, "tracking_id": 77}
    missed = {"ground_truth_id": 2, "time": 20.0}
    targets = _benchmark_trace_targets({"missed_items": [missed], "class_mismatch_items": [mismatch]}, [])
    assert targets == [(missed, 20.0), (mismatch, 10.6)]
    assert mismatch["ai_tracking_id"] == 77
    assert "ai_tracking_id" not in missed


def test_v0554_class_trace_filters_other_tracks_in_top_and_nested_audit() -> None:
    from app.api.routes import _attach_benchmark_trace_diagnosis

    own = {"track_id": 77, "frame_index": 251, "reason": "two-source-two-frame-bicycle"}
    unrelated = {"track_id": 88, "frame_index": 251, "reason": "motor-veto"}
    unknown = {"frame_index": 251, "reason": "unknown-track"}
    diagnosis = {
        "reason": "no-gate-miss",
        "bicycle_context_audit": [own, unrelated, unknown],
        "gate_span_audit": {"anchor_span_candidates": 1, "bicycle_context_audit": [unrelated, own]},
    }
    mismatch = {"ai_tracking_id": 77}
    _attach_benchmark_trace_diagnosis(mismatch, diagnosis)
    attached = mismatch["diagnosis"]
    assert attached["bicycle_context_audit"] == [own]
    assert attached["gate_span_audit"]["bicycle_context_audit"] == [own]
    assert attached["gate_span_audit"]["anchor_span_candidates"] == 1
    assert diagnosis["bicycle_context_audit"] == [own, unrelated, unknown]
    assert diagnosis["gate_span_audit"]["bicycle_context_audit"] == [unrelated, own]


def test_v0555_class_trace_provenance_identifies_matched_canonical_track() -> None:
    from app.api.routes import _attach_benchmark_trace_diagnosis

    own = {"track_id": 77, "frame_index": 251, "commit_status": "accepted"}
    other = {"track_id": 88, "frame_index": 251, "commit_status": "accepted"}
    diagnosis = {"bicycle_context_audit": [other, own], "bicycle_context_scope": "nearby_tracks"}
    item = {"ai_tracking_id": 77}
    _attach_benchmark_trace_diagnosis(item, diagnosis)
    assert item["diagnosis"]["bicycle_context_scope"] == "matched_track"
    assert item["diagnosis"]["bicycle_context_audit"] == [own]
    assert diagnosis["bicycle_context_scope"] == "nearby_tracks"
    assert diagnosis["bicycle_context_audit"] == [other, own]


def test_v0555_class_trace_missing_track_does_not_claim_nearby_decision() -> None:
    from app.api.routes import _attach_benchmark_trace_diagnosis

    other = {"track_id": 88, "frame_index": 251, "commit_status": "accepted"}
    diagnosis = {"bicycle_context_audit": [other]}
    item = {"ai_tracking_id": None}
    _attach_benchmark_trace_diagnosis(item, diagnosis)
    assert item["diagnosis"]["bicycle_context_scope"] == "nearby_tracks"
    assert item["diagnosis"]["bicycle_context_audit"] == [other]
    assert "bicycle_context_scope" not in diagnosis


def test_v0563_crossing_trace_scopes_signed_event_and_omits_private_fields() -> None:
    from app.api.routes import _attach_benchmark_trace_diagnosis
    own = {"tracking_id": -1, "source_frame_index": 1737, "source_time_seconds": 69.4566,
           "stage": "committed_before_submit", "snapshot_path": "private.jpg", "model_id": 9}
    foreign = {"tracking_id": 88, "source_frame_index": 1737, "source_time_seconds": 69.4566}
    diagnosis = {
        "reason": "crossing_proposal_observed", "diagnosis_scope": {"reason": "matched_track_proposal"},
        "crossing_proposal_audit": {"records": [foreign, own], "backend_persistence": "persisted"},
        "event_delivery_audit": {"records": [dict(own, stage="backend_acknowledged", outcome="deduplicated",
            attempts=1, backend_event_id=12, dedup_reason="secondary-reverse-shadow", response_body="private")],
            "dropped_records": 3, "delivery_drain_complete": True, "pending_events": 0},
    }
    item = {"ai_tracking_id": -1}
    _attach_benchmark_trace_diagnosis(item, diagnosis)
    proposal = item["diagnosis"]["crossing_proposal_audit"]
    receipt = item["diagnosis"]["event_delivery_audit"]
    assert proposal["scope"] == receipt["scope"] == "matched_track"
    assert proposal["backend_persistence"] == "unverified"
    assert proposal["records"] == [{key: own[key] for key in
        ("tracking_id", "source_frame_index", "source_time_seconds", "stage")}]
    assert receipt["records"][0]["backend_event_id"] == 12
    assert "response_body" not in receipt["records"][0] and "snapshot_path" not in receipt["records"][0]
    assert receipt["summary_scope"] == "session_global" and receipt["dropped_records"] == 3
    assert item["diagnosis"]["diagnosis_scope"]["reason"] == "matched_track_proposal"
    assert diagnosis["crossing_proposal_audit"]["records"] == [foreign, own]


def test_v0563_nearby_crossing_trace_cannot_claim_matched_gt_track() -> None:
    from app.api.routes import _attach_benchmark_trace_diagnosis
    foreign = {"tracking_id": 88, "source_time_seconds": 69.4566, "stage": "committed_before_submit"}
    diagnosis = {"reason": "crossing_proposal_observed", "diagnosis_scope": {"reason": "matched_track_proposal"},
                 "crossing_proposal_audit": {"records": [foreign]}}
    missed = {"time": 69.457}
    _attach_benchmark_trace_diagnosis(missed, diagnosis)
    assert missed["diagnosis"]["crossing_proposal_audit"]["scope"] == "nearby_time_window"
    assert missed["diagnosis"]["diagnosis_scope"]["reason"] == "nearby_time_window"
    mismatch = {"ai_tracking_id": -1}
    _attach_benchmark_trace_diagnosis(mismatch, diagnosis)
    assert mismatch["diagnosis"]["crossing_proposal_audit"]["scope"] == "no_proposal_evidence"
    assert mismatch["diagnosis"]["diagnosis_scope"]["reason"] == "nearby_time_window"
    assert diagnosis["diagnosis_scope"]["reason"] == "matched_track_proposal"


def test_v0563_crossing_trace_bounds_malformed_and_extra_records_without_changing_scores() -> None:
    from app.api.routes import _attach_benchmark_trace_diagnosis
    from app.benchmarking import match_crossings
    from types import SimpleNamespace
    gt = SimpleNamespace(id=1, source_time_seconds=10.0, direction="out", vehicle_type="car")
    event = SimpleNamespace(id=12, source_time_seconds=10.1, direction="out", vehicle_type="truck", tracking_id=-1)
    report = match_crossings([gt], [event], 0.75)
    scores = {key: report[key] for key in ("matched", "missed", "false_positives", "class_accuracy")}
    item = report["class_mismatch_items"][0]
    item["ai_tracking_id"] = -1
    records = [None, {"tracking_id": True}, {"tracking_id": "-1"}] + [
        {"tracking_id": -1, "source_frame_index": frame, "stage": "backend_acknowledged"} for frame in range(10)]
    diagnosis = {"event_delivery_audit": {"records": records}, "crossing_proposal_audit": {"records": "invalid"}}
    _attach_benchmark_trace_diagnosis(item, diagnosis)
    audit = item["diagnosis"]["event_delivery_audit"]
    assert len(audit["records"]) == 8 and audit["truncated"] is True
    assert [record["source_frame_index"] for record in audit["records"]] == list(range(2, 10))
    assert item["diagnosis"]["crossing_proposal_audit"]["records"] == []
    assert scores == {key: report[key] for key in scores}
    assert len(diagnosis["event_delivery_audit"]["records"]) == 13


def test_v0555_event_refreshes_session_and_bucket_after_another_delivery() -> None:
    """Sequential identity-map regression; SQLite does not prove row locking."""
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session
    from app.models.all_models import CountingSession, VehicleCount, VehicleEvent

    with _dedup_event_database() as db:
        db.expire_on_commit = False
        db.autoflush = False
        _submit_dedup_event(db)
        cached_session = db.get(CountingSession, 1)
        cached_bucket = db.scalar(select(VehicleCount))
        assert cached_session.total_vehicles == cached_bucket.count == 1
        with Session(db.get_bind(), expire_on_commit=False, autoflush=False) as other:
            _submit_dedup_event(other, source_time_seconds=20.0, source_frame_index=501)
        assert cached_session.total_vehicles == cached_bucket.count == 1

        _submit_dedup_event(db, source_time_seconds=30.0, source_frame_index=751)
        assert cached_session.total_vehicles == 3
        assert cached_bucket.count == 3
        assert db.scalar(select(func.count()).select_from(VehicleEvent)) == 3


def test_v0555_finish_refreshes_first_end_time_after_another_finish() -> None:
    """Refresh a stale session before applying an idempotent finish retry."""
    from sqlalchemy.orm import Session
    from app.api.routes import SessionFinish, internal_session_finish, settings
    from app.models.all_models import CountingSession

    with _dedup_event_database() as db:
        db.expire_on_commit = False
        db.autoflush = False
        _submit_dedup_event(db)
        cached_session = db.get(CountingSession, 1)
        assert cached_session.ended_at is None
        with Session(db.get_bind(), expire_on_commit=False, autoflush=False) as other:
            internal_session_finish(1, SessionFinish(status="completed", total_vehicles=3), settings.ai_shared_token, other)
            first_finished = other.get(CountingSession, 1)
            other.refresh(first_finished)
            first_end_time = first_finished.ended_at
        assert cached_session.ended_at is None

        internal_session_finish(1, SessionFinish(status="completed", total_vehicles=3), settings.ai_shared_token, db)
        assert cached_session.ended_at == first_end_time
        assert cached_session.total_vehicles == 1
        assert cached_session.dedup_suppressed_events == 2


def test_v0555_event_and_finish_lock_same_camera_then_refresh_session(monkeypatch) -> None:
    """Compile actual lock statements; no PostgreSQL concurrency simulation."""
    from sqlalchemy.dialects import postgresql
    from app.api.routes import SessionFinish, internal_session_finish, settings
    from app.models.all_models import Camera, CountingSession

    with _dedup_event_database() as db:
        locked = []
        scalar = db.scalar

        def record_scalar(statement, *args, **kwargs):
            if getattr(statement, "_for_update_arg", None) is not None:
                locked.append(statement)
            return scalar(statement, *args, **kwargs)

        monkeypatch.setattr(db, "scalar", record_scalar)
        _submit_dedup_event(db)
        internal_session_finish(1, SessionFinish(status="completed", total_vehicles=1), settings.ai_shared_token, db)
        assert [statement.column_descriptions[0]["entity"] for statement in locked] == [Camera, CountingSession, Camera, CountingSession]
        for statement in locked:
            assert statement.get_execution_options()["populate_existing"] is True
            assert str(statement.compile(dialect=postgresql.dialect())).endswith("FOR UPDATE")


def test_v0554_class_trace_unknown_track_keeps_nearby_evidence_for_review() -> None:
    from app.api.routes import _attach_benchmark_trace_diagnosis

    diagnosis = {"bicycle_context_audit": [{"track_id": 77}], "gate_span_audit": {"bicycle_context_audit": [{"track_id": 88}]}}
    item = {"ai_tracking_id": None}
    _attach_benchmark_trace_diagnosis(item, diagnosis)
    assert item["diagnosis"]["bicycle_context_audit"] == diagnosis["bicycle_context_audit"]
    assert item["diagnosis"]["gate_span_audit"] == diagnosis["gate_span_audit"]
    assert item["diagnosis"]["bicycle_context_scope"] == "nearby_tracks"
    assert "bicycle_context_scope" not in diagnosis


def test_v0554_class_mismatch_report_fetches_trace_without_gate_miss(monkeypatch) -> None:
    from types import SimpleNamespace
    from app.api.routes import _build_benchmark_report
    from app.models.all_models import CountingBenchmark, GroundTruthCrossing

    with _dedup_event_database() as db:
        event, _ = _submit_dedup_event(db, source_time_seconds=10.6203)
        db.add(CountingBenchmark(id=1, camera_id=1, session_id=1, name="Semantic trace regression", source_url="clip.mp4"))
        db.flush()
        db.add(GroundTruthCrossing(benchmark_id=1, source_time_seconds=10.0, vehicle_type="bicycle", direction="in"))
        db.commit()
        calls = []
        own = {"track_id": 10, "frame_index": 251, "reason": "motor-veto"}
        other = {"track_id": 99, "frame_index": 251, "reason": "two-source-two-frame-bicycle"}

        def trace_post(_url, **kwargs):
            calls.append(kwargs["json"])
            return SimpleNamespace(is_success=True, json=lambda: {
                "available": True,
                "items": [{"reason": "class-audit", "bicycle_context_audit": [other, own], "gate_span_audit": {"bicycle_context_audit": [other, own]}}],
            })

        monkeypatch.setattr("app.api.routes.httpx.post", trace_post)
        report = _build_benchmark_report(1, db)
        assert calls[0]["times"] == [event.source_time_seconds]
        assert calls[0]["tracking_ids"] == [10]
        assert report["matched"] == 1
        assert report["missed"] == 0
        assert report["false_positives"] == 0
        assert report["class_accuracy"] == 0.0
        assert report["miss_reason_counts"] == {}
        assert report["trace_available"] is True
        semantic = report["class_mismatch_items"][0]
        assert semantic["ai_tracking_id"] == 10
        assert semantic["diagnosis"]["bicycle_context_audit"] == [own]
        assert semantic["diagnosis"]["gate_span_audit"]["bicycle_context_audit"] == [own]


def test_v0556_diagnostics_metadata_whitelist_distinguishes_snapshot_and_current_config() -> None:
    from types import SimpleNamespace
    from app.api.routes import _benchmark_export_metadata

    session = SimpleNamespace(id=9, camera_id=1, model_id=2, status="completed", source_url="clip1.mp4", secret="session-private")
    camera = SimpleNamespace(id=1, source_type="video", confidence_threshold=0.06, line_x1=0.40, line_x2=0.85, secret="camera-private")
    model = SimpleNamespace(id=2, name="Detector", version="custom", architecture="YOLO", model_path="/private/weights.pt", secret="model-private")
    benchmark = {"geometry": {"line_x1": 0.32, "line_x2": 0.84}, "tolerance_seconds": 0.75}
    session_payload, config = _benchmark_export_metadata(session, camera, model, benchmark)
    assert session_payload["source_url"] == "clip1.mp4"
    assert "secret" not in session_payload
    assert config["benchmark_snapshot"]["geometry"] == {"line_x1": 0.32, "line_x2": 0.84}
    assert config["current_camera"]["geometry"] == {"line_x1": 0.40, "line_x2": 0.85}
    assert config["session_model"] == {"id": 2, "name": "Detector", "version": "custom", "architecture": "YOLO"}
    assert "model_path" not in config["session_model"]
    assert "environment" in config["inference_settings"]
    assert "current" in config["inference_settings"]


def test_v0556_export_route_downloads_one_snapshot_without_changing_counts(monkeypatch) -> None:
    from io import BytesIO
    import json
    from types import SimpleNamespace
    from zipfile import ZipFile
    from sqlalchemy import func, select
    from app.api.routes import export_benchmark
    from app.models.all_models import CountingBenchmark, CountingSession, GroundTruthCrossing, VehicleEvent

    with _dedup_event_database() as db:
        event, _ = _submit_dedup_event(db)
        db.add(CountingBenchmark(id=1, camera_id=1, session_id=1, name="Export regression", source_url="rtsp://user:password@cam/live?token=private"))
        db.flush()
        db.add(GroundTruthCrossing(benchmark_id=1, source_time_seconds=10.0, vehicle_type="bicycle", direction="in", note="Xe đạp"))
        db.commit()
        monkeypatch.setattr("app.api.routes.httpx.post", lambda *_args, **_kwargs: SimpleNamespace(is_success=False))
        trace = b'{"source_time_seconds":10.0,"frame_index":251,"tracks":1}\n'
        monkeypatch.setattr("app.api.routes._fetch_benchmark_export_trace", lambda session_id: (trace, "available"))
        response = export_benchmark(1, db)
        assert response.media_type == "application/zip"
        assert response.headers["Cache-Control"] == "no-store"
        assert "traffic-ai-benchmark-1-session-1.zip" in response.headers["Content-Disposition"]
        with ZipFile(BytesIO(response.body)) as zipped:
            report = json.loads(zipped.read("report.json"))
            assert report["matched"] == 1
            assert report["class_accuracy"] == 0.0
            assert report["benchmark"]["source_url"] == "rtsp://cam/live"
            assert json.loads(zipped.read("events.json"))[0]["id"] == event.id
            assert json.loads(zipped.read("ground-truth.json"))[0]["vehicle_type"] == "bicycle"
            assert zipped.read("benchmark-trace.jsonl") == trace
            assert json.loads(zipped.read("manifest.json"))["trace"]["available"] is True
        assert db.get(CountingSession, 1).total_vehicles == 1
        assert db.scalar(select(func.count()).select_from(VehicleEvent)) == 1
        assert db.scalar(select(func.count()).select_from(GroundTruthCrossing)) == 1


def test_v0556_export_missing_benchmark_fails_before_trace_download(monkeypatch) -> None:
    import pytest
    from fastapi import HTTPException
    from app.api.routes import export_benchmark

    def forbidden_trace(_session_id):
        raise AssertionError("An unknown benchmark must not request a trace")

    monkeypatch.setattr("app.api.routes._fetch_benchmark_export_trace", forbidden_trace)
    with _dedup_event_database() as db:
        with pytest.raises(HTTPException) as error:
            export_benchmark(999, db)
        assert error.value.status_code == 404


def test_v0556_export_trace_transport_handles_oversized_missing_and_empty_sources(monkeypatch) -> None:
    """Transport fixtures exercise optional failures; no real AI HTTP is used."""
    from contextlib import nullcontext
    from types import SimpleNamespace
    from app.api.routes import _fetch_benchmark_export_trace

    requests = []
    response = None

    def stream(method, url, **options):
        requests.append((method, url, options))
        if url.endswith("/download-gzip"):
            return nullcontext(SimpleNamespace(status_code=404, is_success=False, headers={}))
        return nullcontext(response)

    monkeypatch.setattr("app.api.routes.httpx.stream", stream)
    monkeypatch.setattr("app.api.routes.BENCHMARK_TRACE_EXPORT_MAX_BYTES", 5)
    for status_code, announced_bytes, chunks, reason in (
        (404, "0", [], "not_found"),
        (503, "0", [], "http_error_503"),
        (200, "6", [], "too_large"),
        (200, "0", [b"123", b"456"], "too_large"),
        (200, "0", [], "empty"),
        (200, "invalid", [b"12345"], "available"),
    ):
        response = SimpleNamespace(
            status_code=status_code, is_success=status_code == 200,
            headers={"Content-Length": announced_bytes}, iter_bytes=lambda **_kwargs: iter(chunks),
        )
        payload, actual_reason = _fetch_benchmark_export_trace(9)
        assert actual_reason == reason
        assert payload == (b"12345" if reason == "available" else None)
    assert all(request[0] == "GET" and request[1].rsplit("/", 1)[-1] in {"download", "download-gzip"} for request in requests)
    assert [request[1].rsplit("/", 1)[-1] for request in requests] == ["download-gzip", "download"] * 6
    assert all(request[2] == {"timeout": 8.0, "follow_redirects": False} for request in requests)


def test_v0558_numeric_event_clock_rejects_nonfinite_source_seconds() -> None:
    import pytest
    from pydantic import ValidationError
    from app.schemas.event import VehicleEventCreate

    for source_time in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValidationError):
            VehicleEventCreate(camera_id=1, vehicle_type="motorcycle", confidence=0.8,
                               source_time_seconds=source_time)


def test_v0558_numeric_event_clock_preserves_optional_and_finite_inputs() -> None:
    import pytest
    from pydantic import ValidationError
    from app.schemas.event import VehicleEventCreate

    base = dict(camera_id=1, vehicle_type="motorcycle", confidence=0.8)
    assert VehicleEventCreate(**base).source_time_seconds is None
    for source_time in (None, 0.0, 10.6203):
        assert VehicleEventCreate(**base, source_time_seconds=source_time).source_time_seconds == source_time
    with pytest.raises(ValidationError):
        VehicleEventCreate(**base, source_time_seconds=-0.01)


def test_v0558_numeric_ground_truth_clock_rejects_nonfinite_inputs() -> None:
    import pytest
    from pydantic import ValidationError
    from app.api.routes import GroundTruthMarkCreate

    for source_time in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValidationError):
            GroundTruthMarkCreate(source_time_seconds=source_time)


def test_v0558_numeric_ground_truth_clock_keeps_finite_clamp_compatibility() -> None:
    from app.api.routes import GroundTruthMarkCreate

    # Finite negative values remain accepted here: the existing mark route owns
    # the clamp to zero before computing the source-frame index.
    for source_time in (-1.0, 0.0, 641.981):
        mark = GroundTruthMarkCreate(source_time_seconds=source_time)
        assert mark.source_time_seconds == source_time
        assert mark.vehicle_type.value == "motorcycle"
        assert mark.direction.value == "unknown"


def test_v0558_numeric_session_finish_rejects_nonfinite_source_metadata() -> None:
    import pytest
    from pydantic import ValidationError
    from app.api.routes import SessionFinish

    for field in ("average_fps", "source_fps", "source_duration_seconds"):
        for value in (float("nan"), float("inf"), float("-inf")):
            with pytest.raises(ValidationError):
                SessionFinish(status="completed", **{field: value})


def test_v0558_numeric_session_finish_keeps_optional_and_finite_metadata() -> None:
    from app.api.routes import SessionFinish

    omitted = SessionFinish(status="completed")
    assert omitted.average_fps is None
    assert omitted.source_fps is None
    assert omitted.source_duration_seconds is None
    for field in ("average_fps", "source_fps", "source_duration_seconds"):
        for value in (None, -1.0, 0.0, 25.0, 946.0):
            assert getattr(SessionFinish(status="completed", **{field: value}), field) == value


def test_v0558_numeric_benchmark_tolerance_rejects_nonfinite_inputs() -> None:
    import pytest
    from pydantic import ValidationError
    from app.api.routes import BenchmarkCreate, BenchmarkUpdate

    for tolerance in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValidationError):
            BenchmarkCreate(session_id=1, tolerance_seconds=tolerance)
        with pytest.raises(ValidationError):
            BenchmarkUpdate(tolerance_seconds=tolerance)


def test_v0558_numeric_benchmark_tolerance_keeps_finite_route_clamp_inputs() -> None:
    from app.api.routes import BenchmarkCreate, BenchmarkUpdate

    assert BenchmarkCreate(session_id=1).tolerance_seconds == 0.75
    # Preserve finite out-of-range inputs for the existing route's 0.05–3.0
    # clamp; the API's scoring window does not change in this upgrade.
    for tolerance in (-1.0, 0.0, 0.05, 0.75, 3.0, 4.0):
        assert BenchmarkCreate(session_id=1, tolerance_seconds=tolerance).tolerance_seconds == tolerance
        assert BenchmarkUpdate(tolerance_seconds=tolerance).tolerance_seconds == tolerance


def test_v0559_stop_acknowledgment_keeps_live_and_draining_sessions_open() -> None:
    from app.api.routes import _stop_completion_matches_session

    for status_value in ('starting', 'warming', 'running', 'draining'):
        assert not _stop_completion_matches_session(
            {'camera_id': 1, 'session_id': 163, 'status': status_value, 'pending_events': 1}, 1, 163,
        )


def test_v0559_stop_acknowledgment_requires_same_camera_and_session() -> None:
    from app.api.routes import _stop_completion_matches_session

    assert not _stop_completion_matches_session({'camera_id': 2, 'session_id': 163, 'status': 'stopped'}, 1, 163)
    assert not _stop_completion_matches_session({'camera_id': 1, 'session_id': 162, 'status': 'completed'}, 1, 163)
    assert not _stop_completion_matches_session({}, 1, 163)
    assert not _stop_completion_matches_session(None, 1, 163)


def test_v0559_legacy_terminal_stop_with_inflight_events_is_not_complete() -> None:
    from app.api.routes import _stop_completion_matches_session

    for status_value in ('completed', 'stopped'):
        assert not _stop_completion_matches_session(
            {'camera_id': 1, 'session_id': 163, 'status': status_value, 'pending_events': 1}, 1, 163,
        )


def test_v0559_settled_terminal_stop_and_explicit_failure_remain_terminal() -> None:
    from app.api.routes import _stop_completion_matches_session

    for status_value in ('completed', 'stopped', 'error'):
        assert _stop_completion_matches_session(
            {'camera_id': 1, 'session_id': 163, 'status': status_value, 'pending_events': 0}, 1, 163,
        )
    assert _stop_completion_matches_session({'camera_id': 1, 'session_id': 163, 'status': 'error', 'pending_events': 1}, 1, 163)
    assert _stop_completion_matches_session({'camera_id': 1, 'session_id': 163, 'status': 'stopped'}, 1, None)


def test_v0562_signed_canonical_event_keeps_tracking_and_source_clock() -> None:
    from app.schemas.event import VehicleEventCreate

    event = VehicleEventCreate(
        camera_id=1, session_id=167, tracking_id=-1,
        vehicle_type="motorcycle", direction="in", confidence=.9,
        source_frame_index=7273, source_time_seconds=290.88,
        crossing_method="direct", crossing_x=.5, crossing_y=.6,
    )
    assert event.tracking_id == -1 and event.session_id == 167
    assert event.source_frame_index == 7273 and event.source_time_seconds == 290.88
    assert event.vehicle_type.value == "motorcycle" and event.direction.value == "in"
