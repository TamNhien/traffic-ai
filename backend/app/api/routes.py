from datetime import datetime, timedelta, timezone

import httpx2 as httpx
import json
import re
import time
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.geometry import validate_counting_geometry
from app.benchmarking import (
    BENCHMARK_TRACE_EXPORT_MAX_BYTES, BenchmarkTraceArchive, BenchmarkTraceTooLarge,
    build_benchmark_export, match_crossings, read_benchmark_trace_chunks,
)
from app.models.all_models import AIModel, Camera, CameraStatus, CountingBenchmark, CountingSession, DatasetRecord, Direction, GroundTruthCrossing, SessionStatus, TrainingRun, VehicleCount, VehicleEvent, VehicleType
from app.schemas.camera import CameraCreate, CameraRead, CameraUpdate
from app.schemas.event import VehicleEventCreate, VehicleEventRead

router = APIRouter(prefix="/api")


class DatasetCreate(BaseModel):
    name: str
    camera_id: int
    every_n_frames: int = 15
    max_images: int = 600
    smart_dedupe: bool = True
    min_change_ratio: float = 0.008


class DatasetAction(BaseModel):
    confidence: float = 0.25
    train_ratio: float = 0.70
    val_ratio: float = 0.20
    seed: int = 2026


class AnnotationBulkAccept(BaseModel):
    min_confidence: float = 0.70


class TrainingCreate(BaseModel):
    dataset_id: int
    base_model: str = "yolo26s.pt"
    epochs: int = 80
    imgsz: int = 640
    batch: int = 8
    device: str = "auto"


class AnnotationUpdate(BaseModel):
    boxes: list[dict] = []
    reviewed: bool = True
    difficult: bool = False




def _vehicle_family_value(value) -> str:
    label = str(getattr(value, "value", value))
    if label in {"bicycle", "motorcycle"}:
        return "two-wheel"
    if label in {"car", "bus", "truck"}:
        return "four-wheel"
    return label

def _dataset_slug(name: str) -> str:
    value = re.sub(r"[^a-z0-9_-]+", "-", name.strip().lower())
    value = re.sub(r"-+", "-", value).strip("-_")
    if not value:
        raise HTTPException(status_code=422, detail="Tên dataset không hợp lệ")
    return value[:64]


def _dataset_payload(row: DatasetRecord) -> dict:
    return {
        "id": row.id, "name": row.name, "slug": row.slug, "source_camera_id": row.source_camera_id,
        "source_url": row.source_url, "root_path": row.root_path, "status": row.status,
        "sample_every_n_frames": row.sample_every_n_frames, "image_count": row.image_count,
        "labeled_images": row.labeled_images, "box_count": row.box_count,
        "train_count": row.train_count, "val_count": row.val_count, "test_count": row.test_count,
        "reviewed_images": row.reviewed_images, "difficult_images": row.difficult_images,
        "classes": json.loads(row.classes_json or "[]"), "created_at": row.created_at, "updated_at": row.updated_at,
    }


def _training_payload(row: TrainingRun) -> dict:
    return {
        "id": row.id, "dataset_id": row.dataset_id, "base_model": row.base_model, "status": row.status,
        "epochs": row.epochs, "imgsz": row.imgsz, "batch": row.batch_size, "device": row.device,
        "current_epoch": row.current_epoch, "progress": row.progress, "precision": row.precision,
        "recall": row.recall, "map50": row.map50, "map50_95": row.map50_95,
        "best_model_path": row.best_model_path, "last_error": row.last_error,
        "started_at": row.started_at, "ended_at": row.ended_at, "created_at": row.created_at,
    }


def _benchmark_payload(row: CountingBenchmark, mark_count: int = 0) -> dict:
    return {
        "id": row.id,
        "camera_id": row.camera_id,
        "session_id": row.session_id,
        "name": row.name,
        "source_url": row.source_url,
        "source_fps": row.source_fps,
        "source_duration_seconds": row.source_duration_seconds,
        "geometry": {
            "line_x1": row.line_x1, "line_y1": row.line_y1,
            "line_x2": row.line_x2, "line_y2": row.line_y2,
            "road_x1": row.road_x1, "road_y1": row.road_y1,
            "road_x2": row.road_x2, "road_y2": row.road_y2,
            "road_x3": row.road_x3, "road_y3": row.road_y3,
            "road_x4": row.road_x4, "road_y4": row.road_y4,
        },
        "tolerance_seconds": row.tolerance_seconds,
        "mark_count": mark_count,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _ground_truth_payload(row: GroundTruthCrossing) -> dict:
    return {
        "id": row.id,
        "benchmark_id": row.benchmark_id,
        "source_time_seconds": row.source_time_seconds,
        "source_frame_index": row.source_frame_index,
        "vehicle_type": row.vehicle_type,
        "direction": row.direction,
        "note": row.note,
        "created_at": row.created_at,
    }


class SessionFinish(BaseModel):
    status: str
    total_vehicles: int = 0
    average_fps: float | None = Field(default=None, allow_inf_nan=False)
    human_guard_rejections: int = 0
    source_fps: float | None = Field(default=None, allow_inf_nan=False)
    source_duration_seconds: float | None = Field(default=None, allow_inf_nan=False)
    last_error: str | None = None


class BenchmarkCreate(BaseModel):
    session_id: int
    name: str | None = None
    tolerance_seconds: float = Field(default=0.75, allow_inf_nan=False)
    clone_marks_from_benchmark_id: int | None = None


class BenchmarkUpdate(BaseModel):
    tolerance_seconds: float = Field(allow_inf_nan=False)


class BenchmarkCloneMarks(BaseModel):
    source_benchmark_id: int


class GroundTruthMarkCreate(BaseModel):
    source_time_seconds: float = Field(allow_inf_nan=False)
    direction: Direction = Direction.unknown
    vehicle_type: VehicleType = VehicleType.motorcycle
    note: str | None = None


class GroundTruthMarkUpdate(BaseModel):
    direction: Direction | None = None
    vehicle_type: VehicleType | None = None
    note: str | None = None


def _assert_ai_token(token: str | None) -> None:
    if token != settings.ai_shared_token:
        raise HTTPException(status_code=401, detail="Invalid AI service token")


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    """Health endpoint chỉ kiểm tra Backend + Database.

    Endpoint này được Docker healthcheck sử dụng nên tuyệt đối không phụ thuộc
    AI Service. AI Service chỉ được phép khởi động sau khi Backend healthy;
    nếu healthcheck Backend lại gọi ngược sang AI Service sẽ tạo phụ thuộc vòng
    và có thể làm container Backend bị đánh dấu unhealthy dù API đã sẵn sàng.
    """
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "service": "backend",
        "database": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/system/status")
def system_status(db: Session = Depends(get_db)) -> dict:
    """Trạng thái mở rộng cho Dashboard, bao gồm AI Service nếu sẵn sàng."""
    db.execute(text("SELECT 1"))
    ai_payload = None
    try:
        response = httpx.get(f"{settings.ai_service_url}/health", timeout=1.5)
        if response.is_success:
            ai_payload = response.json()
    except Exception:
        pass
    return {
        "status": "ok",
        "service": "backend",
        "database": "ok",
        "ai_service": "ready" if ai_payload else "unavailable",
        "ai": ai_payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)) -> dict:
    total_cameras = db.scalar(select(func.count(Camera.id))) or 0
    active_cameras = db.scalar(select(func.count(Camera.id)).where(Camera.status == CameraStatus.active)) or 0
    total_events = db.scalar(select(func.count(VehicleEvent.id))) or 0
    running_sessions = db.scalar(select(func.count(CountingSession.id)).where(CountingSession.status == SessionStatus.running)) or 0
    by_type_rows = db.execute(select(VehicleEvent.vehicle_type, func.count(VehicleEvent.id)).group_by(VehicleEvent.vehicle_type)).all()
    by_direction_rows = db.execute(select(VehicleEvent.direction, func.count(VehicleEvent.id)).group_by(VehicleEvent.direction)).all()
    return {
        "total_cameras": total_cameras,
        "active_cameras": active_cameras,
        "total_events": total_events,
        "running_sessions": running_sessions,
        "by_vehicle_type": {row[0].value if hasattr(row[0], "value") else str(row[0]): row[1] for row in by_type_rows},
        "by_direction": {row[0].value if hasattr(row[0], "value") else str(row[0]): row[1] for row in by_direction_rows},
    }


@router.get("/cameras", response_model=list[CameraRead])
def list_cameras(db: Session = Depends(get_db)) -> list[Camera]:
    return list(db.scalars(select(Camera).order_by(Camera.id)).all())


@router.post("/cameras", response_model=CameraRead, status_code=status.HTTP_201_CREATED)
def create_camera(payload: CameraCreate, db: Session = Depends(get_db)) -> Camera:
    camera_values = payload.model_dump()
    geometry_error = validate_counting_geometry(camera_values)
    if geometry_error:
        raise HTTPException(status_code=422, detail=geometry_error)
    camera = Camera(**camera_values)
    db.add(camera)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Camera code already exists") from exc
    db.refresh(camera)
    return camera


@router.patch("/cameras/{camera_id}", response_model=CameraRead)
def update_camera(camera_id: int, payload: CameraUpdate, db: Session = Depends(get_db)) -> Camera:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return camera

    running = db.scalar(select(CountingSession.id).where(
        CountingSession.camera_id == camera_id,
        CountingSession.status == SessionStatus.running,
    ).limit(1))
    runtime_keys = {
        "source_type", "source_url", "confidence_threshold",
        "line_x1", "line_y1", "line_x2", "line_y2",
        "road_x1", "road_y1", "road_x2", "road_y2", "road_x3", "road_y3", "road_x4", "road_y4",
    }
    if running and runtime_keys.intersection(changes):
        raise HTTPException(status_code=409, detail="Hãy dừng AI trước khi đổi nguồn hoặc vùng đếm.")

    geometry_keys = {
        "line_x1", "line_y1", "line_x2", "line_y2",
        "road_x1", "road_y1", "road_x2", "road_y2", "road_x3", "road_y3", "road_x4", "road_y4",
    }
    if geometry_keys.intersection(changes):
        candidate_geometry = {key: changes.get(key, getattr(camera, key)) for key in geometry_keys}
        geometry_error = validate_counting_geometry(candidate_geometry)
        if geometry_error:
            raise HTTPException(status_code=422, detail=geometry_error)

    source_changed = bool({"source_type", "source_url"}.intersection(changes))
    for key, value in changes.items():
        setattr(camera, key, value)
    if source_changed and camera.status == CameraStatus.error:
        camera.status = CameraStatus.inactive
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Camera code already exists") from exc
    db.refresh(camera)
    return camera


@router.get("/sources/videos")
def list_video_sources() -> list[dict]:
    try:
        response = httpx.get(f"{settings.ai_service_url}/sources/videos", timeout=3.0)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Không đọc được danh sách video từ AI Service: {exc}") from exc


@router.get("/cameras/{camera_id}/source-status")
def camera_source_status(camera_id: int, probe: bool = Query(default=False), db: Session = Depends(get_db)) -> dict:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    try:
        response = httpx.post(
            f"{settings.ai_service_url}/sources/validate",
            params={"probe": str(probe).lower()},
            json={"source_type": camera.source_type.value, "source_url": camera.source_url},
            timeout=8.0 if probe else 3.0,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Không kiểm tra được nguồn camera/video: {exc}") from exc


@router.get("/cameras/{camera_id}/preview.jpg")
def camera_preview(camera_id: int, db: Session = Depends(get_db)) -> Response:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    try:
        response = httpx.post(
            f"{settings.ai_service_url}/sources/preview",
            json={"source_type": camera.source_type.value, "source_url": camera.source_url},
            timeout=12.0,
        )
        response.raise_for_status()
        return Response(content=response.content, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Không lấy được ảnh xem trước: {exc}") from exc


@router.get("/events", response_model=list[VehicleEventRead])
def list_events(
    limit: int = Query(default=50, ge=1, le=500),
    session_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> list[VehicleEvent]:
    stmt = select(VehicleEvent)
    if session_id is not None:
        stmt = stmt.where(VehicleEvent.session_id == session_id)
    return list(db.scalars(stmt.order_by(VehicleEvent.detected_at.desc()).limit(limit)).all())


@router.post("/events", response_model=VehicleEventRead, status_code=status.HTTP_201_CREATED)
def create_event(payload: VehicleEventCreate, db: Session = Depends(get_db)) -> VehicleEvent:
    if db.get(Camera, payload.camera_id) is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    event = VehicleEvent(**payload.model_dump(exclude_none=True))
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/models")
def list_models(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(AIModel).order_by(AIModel.id.desc())).all()
    return [{
        "id": row.id, "name": row.name, "version": row.version, "architecture": row.architecture,
        "model_path": row.model_path, "precision": row.precision, "recall": row.recall,
        "map50": row.map50, "map50_95": row.map50_95, "is_active": row.is_active, "created_at": row.created_at,
    } for row in rows]


@router.get("/sessions")
def list_sessions(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(CountingSession).order_by(CountingSession.id.desc()).limit(limit)).all()
    return [{
        "id": row.id, "camera_id": row.camera_id, "model_id": row.model_id,
        "started_at": row.started_at, "ended_at": row.ended_at, "status": row.status,
        "total_vehicles": row.total_vehicles, "worker_total_vehicles": row.worker_total_vehicles,
        "dedup_suppressed_events": row.dedup_suppressed_events, "human_guard_rejections": row.human_guard_rejections,
        "average_fps": row.average_fps,
        "source_url": row.source_url, "source_fps": row.source_fps, "source_duration_seconds": row.source_duration_seconds,
    } for row in rows]


@router.post("/cameras/{camera_id}/start")
def start_camera(camera_id: int, db: Session = Depends(get_db)) -> dict:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    geometry_values = {
        key: getattr(camera, key) for key in (
            "line_x1", "line_y1", "line_x2", "line_y2",
            "road_x1", "road_y1", "road_x2", "road_y2", "road_x3", "road_y3", "road_x4", "road_y4",
        )
    }
    geometry_error = validate_counting_geometry(geometry_values)
    if geometry_error:
        raise HTTPException(status_code=422, detail=f"Cấu hình vùng đếm chưa hợp lệ: {geometry_error}")
    running = db.scalar(select(CountingSession).where(CountingSession.camera_id == camera_id, CountingSession.status == SessionStatus.running).order_by(CountingSession.id.desc()))
    if running:
        # Reconcile stale DB state with the real AI registry. This makes replaying
        # the same MP4 reliable even when a previous finish callback was lost.
        ai_is_running = False
        try:
            probe = httpx.get(f"{settings.ai_service_url}/pipelines/{camera_id}", timeout=2.0)
            if probe.is_success:
                ai_state = probe.json()
                ai_is_running = ai_state.get("status") in {"starting", "warming", "running", "draining"}
        except Exception:
            ai_is_running = False
        if ai_is_running:
            raise HTTPException(status_code=409, detail="Camera already has a running session")
        running.status = SessionStatus.completed
        running.ended_at = datetime.now(timezone.utc)
        camera.status = CameraStatus.inactive
        db.commit()
    # Preflight source before creating a session. This prevents a stale video path
    # (for example after renaming traffic_video.mp4 -> demo.mp4) from creating an
    # error session and from showing a false "AI started" success message.
    try:
        source_probe = httpx.post(
            f"{settings.ai_service_url}/sources/validate",
            params={"probe": "true" if camera.source_type.value == "video" else "false"},
            json={"source_type": camera.source_type.value, "source_url": camera.source_url},
            timeout=10.0,
        )
        source_probe.raise_for_status()
        source_state = source_probe.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Không kiểm tra được nguồn camera/video: {exc}") from exc
    source_repaired = False
    if not source_state.get("valid"):
        suggestion = source_state.get("suggested_source_url")
        # Nếu video local cũ đã bị đổi tên và thư mục videos chỉ còn đúng một
        # ứng viên, có thể sửa an toàn đường dẫn đã lưu trong PostgreSQL. Nhờ đó
        # camera cũ (ví dụ CAM-001) không tiếp tục giữ tên file đã biến mất.
        if camera.source_type.value == "video" and suggestion:
            try:
                repaired_probe = httpx.post(
                    f"{settings.ai_service_url}/sources/validate",
                    params={"probe": "true"},
                    json={"source_type": "video", "source_url": suggestion},
                    timeout=10.0,
                )
                repaired_probe.raise_for_status()
                repaired_state = repaired_probe.json()
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Không kiểm tra được video gợi ý: {exc}") from exc
            if repaired_state.get("valid"):
                camera.source_url = repaired_state.get("source_url") or suggestion
                if camera.status == CameraStatus.error:
                    camera.status = CameraStatus.inactive
                db.commit()
                db.refresh(camera)
                source_state = repaired_state
                source_repaired = True

        if not source_state.get("valid"):
            detail = source_state.get("message", "Nguồn camera/video không hợp lệ.")
            suggestion = source_state.get("suggested_source_url")
            if suggestion:
                detail += f" Gợi ý nguồn đang có: {suggestion}"
            raise HTTPException(status_code=422, detail=detail)

    model = db.scalar(select(AIModel).where(AIModel.is_active.is_(True)).order_by(AIModel.id.desc()))
    session = CountingSession(camera_id=camera_id, model_id=model.id if model else None, status=SessionStatus.running, source_url=camera.source_url)
    camera.status = CameraStatus.active
    db.add(session)
    db.commit()
    db.refresh(session)
    payload = {
        "camera_id": camera.id,
        "session_id": session.id,
        "model_id": session.model_id,
        "model_path": model.model_path if model else None,
        "source_type": camera.source_type.value,
        "source_url": camera.source_url,
        "confidence_threshold": camera.confidence_threshold,
        "line_x1": camera.line_x1, "line_y1": camera.line_y1,
        "line_x2": camera.line_x2, "line_y2": camera.line_y2,
        "road_x1": camera.road_x1, "road_y1": camera.road_y1,
        "road_x2": camera.road_x2, "road_y2": camera.road_y2,
        "road_x3": camera.road_x3, "road_y3": camera.road_y3,
        "road_x4": camera.road_x4, "road_y4": camera.road_y4,
    }
    try:
        response = httpx.post(f"{settings.ai_service_url}/pipelines/start", json=payload, timeout=10.0)
        response.raise_for_status()
    except Exception as exc:
        session.status = SessionStatus.error
        session.ended_at = datetime.now(timezone.utc)
        latest_session = db.scalar(select(CountingSession).where(
            CountingSession.camera_id == camera_id,
        ).order_by(CountingSession.id.desc()))
        if _session_finish_owns_camera(session, latest_session):
            camera.status = CameraStatus.error
        db.commit()
        raise HTTPException(status_code=502, detail=f"AI service could not start pipeline: {exc}") from exc
    return {"session_id": session.id, "camera_id": camera_id, "source_repaired": source_repaired, "source_url": camera.source_url, "pipeline": response.json()}


def _stop_completion_matches_session(ai_state: dict, camera_id: int, session_id: int | None) -> bool:
    """A stop acknowledgment cannot finish a different or still-draining run."""
    if not isinstance(ai_state, dict):
        return False
    if ai_state.get("camera_id") != camera_id or (session_id is not None and ai_state.get("session_id") != session_id):
        return False
    status_value = ai_state.get("status")
    if status_value not in {"completed", "stopped", "error"}:
        return False
    # Older services can expose a terminal state while HTTP delivery is active.
    return status_value == "error" or ai_state.get("pending_events", 0) == 0


@router.post("/cameras/{camera_id}/stop")
def stop_camera(camera_id: int, db: Session = Depends(get_db)) -> dict:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    expected_session = db.scalar(select(CountingSession).where(
        CountingSession.camera_id == camera_id,
    ).order_by(CountingSession.id.desc()))
    session = expected_session if expected_session is not None and expected_session.status == SessionStatus.running else None
    ai_state = None
    try:
        response = httpx.post(f"{settings.ai_service_url}/pipelines/{camera_id}/stop", timeout=12.0)
        if response.status_code not in (200, 404):
            response.raise_for_status()
        if response.status_code == 200:
            json_reader = getattr(response, "json", None)
            if callable(json_reader):
                ai_state = json_reader()
                if not isinstance(ai_state, dict):
                    raise ValueError("AI stop response must be an object")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI service could not stop pipeline: {exc}") from exc
    if ai_state is not None and not _stop_completion_matches_session(
        ai_state, camera_id, expected_session.id if expected_session is not None else None,
    ):
        return {"status": "draining", "camera_id": camera_id,
                "session_id": ai_state.get("session_id"), "pending_events": ai_state.get("pending_events", 0)}
    if session:
        # The worker finish callback may have committed while this RPC waited.
        db.refresh(session)
        if session.status == SessionStatus.running:
            session.status = {
                "completed": SessionStatus.completed, "error": SessionStatus.error,
            }.get((ai_state or {}).get("status"), SessionStatus.stopped)
            if session.ended_at is None:
                session.ended_at = datetime.now(timezone.utc)
    latest_session = db.scalar(select(CountingSession).where(
        CountingSession.camera_id == camera_id,
    ).order_by(CountingSession.id.desc()))
    if _session_finish_owns_camera(expected_session, latest_session):
        camera.status = CameraStatus.inactive
    db.commit()
    return {"status": (ai_state or {}).get("status", "stopped"), "camera_id": camera_id}


@router.get("/pipelines")
def list_pipelines() -> list[dict]:
    try:
        response = httpx.get(f"{settings.ai_service_url}/pipelines", timeout=3.0)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI service unavailable: {exc}") from exc


@router.get("/cameras/{camera_id}/road-proposal")
def camera_road_proposal(camera_id: int, db: Session = Depends(get_db)) -> dict:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    try:
        response = httpx.get(f"{settings.ai_service_url}/pipelines/{camera_id}/road-proposal", timeout=5.0)
        if response.status_code == 409:
            detail = response.json().get("detail", "Chưa đủ dữ liệu luồng xe để đề xuất Road Zone.")
            raise HTTPException(status_code=409, detail=detail)
        response.raise_for_status()
        return response.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Không lấy được đề xuất Road Zone từ AI Service: {exc}") from exc


def _startup_crossing_signature_duplicate(
    source_time_seconds: float,
    other_time_seconds: float,
    distance: float,
) -> bool:
    """Narrow V0.5.31 guard for one bootstrap vehicle exposed as two raw IDs."""
    return (
        source_time_seconds <= 1.0
        and other_time_seconds <= 1.0
        and abs(source_time_seconds - other_time_seconds) <= 0.45
        and distance <= 0.040
    )


def _two_wheel_rescue_signature_duplicate(
    time_delta: float,
    distance: float,
    current_method: str | None,
    other_method: str | None,
) -> bool:
    """Narrow V0.5.35 cross-ID guard for secondary two-wheel gate events.

    V0.5.34 recovered eight additional GT matches with nine 2W-center rescues,
    but the benchmark also retained near-GT duplicate events. The generic 0.22s
    signature must stay tight for dense traffic, so only a pair involving a
    rescued/interpolated crossing receives a slightly wider time window and a
    tighter spatial requirement. Direct/direct traffic is never widened here.
    """
    methods = {str(current_method or ""), str(other_method or "")}
    if "rescued" in methods:
        return float(time_delta) <= 0.60 and float(distance) <= 0.018
    if methods <= {"interpolated", "rescued"} and "interpolated" in methods:
        return float(time_delta) <= 0.40 and float(distance) <= 0.016
    return False


def _two_wheel_spatial_signature_duplicate(
    time_delta: float,
    distance: float,
    current_method: str | None,
    other_method: str | None,
) -> bool:
    """V0.5.37 second-stage cross-ID signature for very close 2W crossings.

    V0.5.36 benchmark audit showed a small set of unmatched events with nearly
    identical crossing points. We widen time only for secondary crossing methods
    and simultaneously tighten space. Direct/direct traffic keeps the existing
    0.22 s generic guard so dense real motorcycles are never globally collapsed.
    """
    methods = {str(current_method or ""), str(other_method or "")}
    if methods == {"direct"}:
        return False
    if "rescued" in methods:
        # Preserve the existing V0.5.35 region, then admit a longer tail only
        # when the two crossing points are essentially identical.
        if float(time_delta) <= 0.60 and float(distance) <= 0.018:
            return True
        return float(time_delta) <= 0.75 and float(distance) <= 0.012
    if "interpolated" in methods:
        if methods == {"interpolated"}:
            return float(time_delta) <= 0.40 and float(distance) <= 0.016
        return float(time_delta) <= 0.50 and float(distance) <= 0.010
    return False


def _two_wheel_ultra_spatial_signature_duplicate(
    time_delta: float,
    distance: float,
    current_method: str | None,
    other_method: str | None,
) -> bool:
    """V0.5.38 ultra-tight tail for secondary two-wheel duplicate signatures.

    The V0.5.37 benchmark still reports same-point duplicates just beyond the
    0.75 s rescue window.  Extend time only when at least one event is a
    secondary crossing and the normalized crossing points are almost identical.
    Direct/direct traffic is intentionally excluded so two real motorcycles that
    cross the same lane close together are never collapsed by this path.
    """
    methods = {str(current_method or ""), str(other_method or "")}
    if methods == {"direct"}:
        return False
    if "rescued" in methods:
        return float(time_delta) <= 1.02 and float(distance) <= 0.008
    if "interpolated" in methods:
        return float(time_delta) <= 0.90 and float(distance) <= 0.007
    return False




def _secondary_shadow_signature_duplicate(
    time_delta: float,
    distance: float,
    current_method: str | None,
    other_method: str | None,
) -> bool:
    """V0.5.45 precision-first shadow-event guard.

    A direct crossing can be rediscovered by an interpolated/rescued branch after
    an ID switch.  The existing V0.5.35-V0.5.38 guards intentionally leave a
    narrow gap between their medium/ultra spatial tails.  Benchmark #26 shows
    six unmatched events almost on top of an already matched GT crossing, so we
    close only that gap: at least one event must be secondary and the crossing
    points must be extremely close.  Direct/direct traffic is never collapsed.
    """
    methods = {str(current_method or ""), str(other_method or "")}
    if not methods or methods == {"direct"}:
        return False
    if "rescued" in methods:
        return float(time_delta) <= 0.85 and float(distance) <= 0.014
    if "interpolated" in methods:
        return float(time_delta) <= 0.75 and float(distance) <= 0.012
    return False





DIRECT_SECONDARY_SHADOW_LOOKBACK_SECONDS = 1.15
SEMANTIC_FAMILY_SHADOW_LOOKBACK_SECONDS = 1.20


def _cross_class_heavy_signature_duplicate(
    time_delta: float,
    distance: float,
    current_type,
    other_type,
) -> bool:
    """Compare stored Enum members and incoming values using vehicle labels."""
    labels = {
        str(getattr(current_type, "value", current_type)),
        str(getattr(other_type, "value", other_type)),
    }
    return (
        len(labels) == 2
        and labels <= {"car", "bus", "truck"}
        and bool(labels & {"truck", "bus"})
        and float(time_delta) <= 0.85
        and float(distance) <= 0.050
    )


def _semantic_family_shadow_duplicate(
    time_delta: float,
    distance: float,
    current_method: str | None,
    other_method: str | None,
    *,
    same_direction: bool,
    same_class: bool,
) -> bool:
    """V0.5.50 ultra-spatial guard for class-wobble shadows.

    Benchmark #32 still contains six unmatched events essentially on top of an
    already matched crossing.  The older precision guards intentionally require
    exact class, so a single motorcycle that flips MOTORCYCLE <-> BICYCLE (or a
    heavy vehicle that flips CAR <-> TRUCK) can survive as two events after an
    ID switch.  This guard is family-only and therefore deliberately tighter in
    space than the exact-class guards.  Exact-class pairs return False here and
    continue through the existing rules unchanged.
    """
    if same_class:
        return False
    methods = {str(current_method or ""), str(other_method or "")}
    if not methods:
        return False
    if not same_direction:
        if methods == {"direct"}:
            return False
        if "rescued" in methods:
            return float(time_delta) <= 0.60 and float(distance) <= 0.006
        if "interpolated" in methods:
            return float(time_delta) <= 0.50 and float(distance) <= 0.005
        return False
    if methods == {"direct"}:
        return float(time_delta) <= 0.32 and float(distance) <= 0.004
    if "rescued" in methods:
        return float(time_delta) <= SEMANTIC_FAMILY_SHADOW_LOOKBACK_SECONDS and float(distance) <= 0.010
    if "interpolated" in methods:
        return float(time_delta) <= 1.00 and float(distance) <= 0.008
    return False


def _direct_secondary_shadow_duplicate(
    time_delta: float,
    distance: float,
    current_method: str | None,
    other_method: str | None,
) -> bool:
    """V0.5.49 close only direct -> secondary cross-ID shadows.

    The pair must contain exactly one DIRECT event and one secondary event.
    The time window is slightly wider than the generic secondary-shadow guard,
    but the crossing-point radius is much tighter. DIRECT/DIRECT is explicitly
    excluded, preserving dense legitimate traffic.
    """
    methods = {str(current_method or ""), str(other_method or "")}
    if "direct" not in methods or len(methods) != 2:
        return False
    if "rescued" in methods:
        return float(time_delta) <= DIRECT_SECONDARY_SHADOW_LOOKBACK_SECONDS and float(distance) <= 0.008
    if "interpolated" in methods:
        return float(time_delta) <= 0.95 and float(distance) <= 0.007
    return False

def _direct_ultra_spatial_shadow_duplicate(
    time_delta: float,
    distance: float,
    current_method: str | None,
    other_method: str | None,
) -> bool:
    """V0.5.48 close only the tiny direct/direct duplicate tail.

    Benchmark 149/155 still contains events almost on top of a GT-matched event.
    Previous shadow guards intentionally excluded direct/direct traffic.  Keep
    that protection everywhere except an ultra-tight extension beyond the generic
    0.22 s signature: both events must be DIRECT, within 0.42 s and within 0.006
    normalized crossing-point distance.  This is deliberately narrower than the
    secondary shadow rules so dense legitimate traffic remains distinct.
    """
    methods = {str(current_method or ""), str(other_method or "")}
    return methods == {"direct"} and float(time_delta) <= 0.42 and float(distance) <= 0.006

def _secondary_reverse_shadow_duplicate(
    time_delta: float,
    distance: float,
    current_method: str | None,
    other_method: str | None,
) -> bool:
    """V0.5.46 cross-ID reverse shadow guard.

    Opposite-direction direct/direct events can be two real vehicles and are
    therefore never collapsed here.  When one side of the pair is a secondary
    interpolated/rescued rediscovery, however, an ultra-close point and short
    interval is strong evidence that one physical crossing was emitted twice
    with a transient ID/direction flip.
    """
    methods = {str(current_method or ""), str(other_method or "")}
    if not methods or methods == {"direct"}:
        return False
    if "rescued" in methods:
        return float(time_delta) <= 0.70 and float(distance) <= 0.012
    if "interpolated" in methods:
        return float(time_delta) <= 0.55 and float(distance) <= 0.010
    return False


def _crossing_point_distance(payload: VehicleEventCreate, existing: VehicleEvent | None) -> float | None:
    if existing is None:
        return None
    if payload.crossing_x is None or payload.crossing_y is None:
        return None
    if existing.crossing_x is None or existing.crossing_y is None:
        return None
    dx = float(payload.crossing_x) - float(existing.crossing_x)
    dy = float(payload.crossing_y) - float(existing.crossing_y)
    return (dx * dx + dy * dy) ** 0.5


def _same_track_cycle_duplicate_reason(payload: VehicleEventCreate, existing: VehicleEvent | None) -> str | None:
    """Reject only geometrically implausible rapid re-crossings for one canonical track.

    Passage semantics remain intact: a vehicle may cross again later. The guard
    applies inside a short source-video interval, with spatial tails beyond it.
    Same-direction repeats cannot be a second traversal of the same finite line
    without an intervening opposite traversal (or a loop around an endpoint), so
    a repeat inside 4 s is treated as track/gate jitter. Opposite direction uses
    3 s with a close-point tail to 4 s; secondary repeats have a close-point tail
    to 5 s. Source seconds take precedence over fixed frame-count fallbacks.
    """
    if existing is None:
        return None
    frame_delta = None
    time_delta = None
    if payload.source_frame_index is not None and existing.source_frame_index is not None:
        frame_delta = abs(int(payload.source_frame_index) - int(existing.source_frame_index))
    if payload.source_time_seconds is not None and existing.source_time_seconds is not None:
        time_delta = abs(float(payload.source_time_seconds) - float(existing.source_time_seconds))
    distance = _crossing_point_distance(payload, existing)
    same_direction = str(getattr(payload.direction, "value", payload.direction)) == str(getattr(existing.direction, "value", existing.direction))

    # V0.5.46 Precision Closure 9.2.  Benchmark #27 shows that the dominant
    # unmatched events are still same canonical-track repeats.  A single finite
    # gate cannot be crossed twice in the same direction within a few seconds
    # without an intervening opposite traversal (or an implausibly fast loop
    # around an endpoint), so the short-window guard no longer depends on the
    # noisy box-derived crossing point. Genuine later passage cycles stay valid.
    # Source seconds are independent of camera FPS and delivery time. Frames
    # are a fallback only when the pair has no comparable source timestamps.
    if time_delta is not None:
        short_flip, close_flip = time_delta <= 3.0, time_delta <= 4.0
        short_repeat, close_repeat = time_delta <= 4.0, time_delta <= 5.0
    else:
        short_flip = frame_delta is not None and frame_delta <= 75
        close_flip = frame_delta is not None and frame_delta <= 100
        short_repeat = frame_delta is not None and frame_delta <= 100
        close_repeat = frame_delta is not None and frame_delta <= 125
    if not same_direction:
        if short_flip:
            return "same-track-direction-flip"
        extended_close = (
            distance is not None and distance <= 0.030
            and close_flip
        )
        return "same-track-direction-flip" if extended_close else None

    if short_repeat:
        return "same-track-repeat-jitter"
    # Outside the physical short-cycle window, keep a narrow spatial tail for a
    # secondary rediscovery, but never restore lifetime uniqueness.
    if distance is not None and distance <= 0.020:
        method = str(payload.crossing_method or "")
        other_method = str(getattr(existing, "crossing_method", "") or "")
        if {method, other_method} != {"direct"} and close_repeat:
            return "same-track-repeat-jitter"
    return None

def _same_track_delivery_retry(payload: VehicleEventCreate, existing: VehicleEvent | None) -> bool:
    """Return True only when a same-track/same-direction row is a delivery retry.

    Before V0.5.44 the backend treated ``session + tracking_id + direction`` as a
    lifetime-unique key.  That contradicted passage semantics: the same physical
    vehicle can leave, loop around and cross the gate in the same direction again
    while ByteTrack keeps its canonical ID.  Network retries, however, still need
    to be idempotent.  Source frame/time identify the physical crossing, so only
    near-identical source positions are collapsed. Legacy payloads with no source
    coordinates keep the conservative old behaviour.
    """

    if existing is None:
        return False
    if payload.source_time_seconds is not None and existing.source_time_seconds is not None:
        return abs(float(payload.source_time_seconds) - float(existing.source_time_seconds)) <= 0.12
    if payload.source_frame_index is not None and existing.source_frame_index is not None:
        return abs(int(payload.source_frame_index) - int(existing.source_frame_index)) <= 2
    if payload.detected_at is not None and existing.detected_at is not None:
        try:
            return abs((payload.detected_at - existing.detected_at).total_seconds()) <= 0.25
        except TypeError:
            return False
    return True


def _same_track_source_neighbor(payload: VehicleEventCreate, candidates: list[VehicleEvent]) -> VehicleEvent | None:
    """Find the adjacent source passage even when delivery order differs."""
    if not candidates:
        return None
    for name in ("source_time_seconds", "source_frame_index"):
        position = getattr(payload, name)
        comparable = [other for other in candidates if position is not None and getattr(other, name) is not None]
        if comparable:
            return min(comparable, key=lambda other: abs(float(getattr(other, name)) - float(position)))
    return candidates[0]


def _event_session_camera_matches(session: CountingSession, camera_id: int) -> bool:
    """A source passage belongs to the camera that created its session."""
    return int(session.camera_id) == int(camera_id)


def _sync_session_persisted_total(session: CountingSession, persisted_count: int) -> None:
    """Keep stored suppression telemetry correct after deferred event delivery."""
    session.total_vehicles = max(0, int(persisted_count))
    if session.worker_total_vehicles is not None:
        session.dedup_suppressed_events = max(0, int(session.worker_total_vehicles) - session.total_vehicles)


def _session_finish_owns_camera(session: CountingSession | None, latest_session: CountingSession | None) -> bool:
    """A stale replay's remote callback must not change the current camera."""
    return latest_session is None or (session is not None and int(latest_session.id) == int(session.id))


@router.post("/internal/events", response_model=VehicleEventRead, status_code=201)
def internal_event(payload: VehicleEventCreate, response: Response, x_ai_token: str | None = Header(default=None), db: Session = Depends(get_db)) -> VehicleEvent:
    _assert_ai_token(x_ai_token)

    # Serialize signature reads, event writes and hourly bucket updates per
    # camera. Both delivery and finish acquire camera then session, so waiting
    # on another request cannot leave an identity-map copy of the totals stale.
    camera = db.scalar(select(Camera).where(
        Camera.id == payload.camera_id,
    ).with_for_update().execution_options(populate_existing=True))
    # V0.5.54: validate ownership before returning a duplicate or changing
    # counters. A stale worker must not attach another camera's source clock
    # and track IDs to this replay's session.
    session = None
    if payload.session_id is not None:
        session = db.scalar(select(CountingSession).where(
            CountingSession.id == payload.session_id,
        ).with_for_update().execution_options(populate_existing=True))
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        if not _event_session_camera_matches(session, payload.camera_id):
            raise HTTPException(status_code=422, detail="Event camera does not match session camera")
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Event delivery is retried by the AI service. V0.5.44 keeps retries
    # idempotent by source frame/time instead of treating one tracking ID and
    # direction as lifetime-unique. This preserves genuine later passage cycles.
    same_track_events = []
    if payload.session_id is not None and payload.tracking_id is not None:
        same_track_events = list(db.scalars(select(VehicleEvent).where(
            VehicleEvent.session_id == payload.session_id,
            VehicleEvent.tracking_id == payload.tracking_id,
        ).order_by(VehicleEvent.id.desc())).all())
    # A late retry may refer to an older passage after a newer IN/OUT cycle
    # has already been stored. Inspect this track's passage rows, rather than
    # assuming the greatest database ID is the physical crossing being retried.
    for existing in same_track_events:
        if existing.direction == payload.direction and _same_track_delivery_retry(payload, existing):
            response.headers["X-TrafficAI-Deduplicated"] = "1"
            response.headers["X-TrafficAI-Dedup-Reason"] = "same-track-delivery-retry"
            return existing

    # V0.5.45 False Positive Closure 9.1: keep genuine later passage cycles, but
    # close rapid same-track repeats/direction flips that occur at the same gate
    # point. This targets benchmark-proven jitter without restoring a lifetime
    # uniqueness rule for tracking_id.
    if same_track_events:
        recent_same_track = _same_track_source_neighbor(payload, same_track_events)
        cycle_reason = _same_track_cycle_duplicate_reason(payload, recent_same_track)
        if cycle_reason is not None:
            response.headers["X-TrafficAI-Deduplicated"] = "1"
            response.headers["X-TrafficAI-Dedup-Reason"] = cycle_reason
            return recent_same_track

    # Crossing Engine 7.1 cross-ID signature guard. A ByteTrack ID switch can
    # create two canonical IDs for the same physical crossing. Suppress only
    # extremely-near same-direction/same-family signatures so two real vehicles
    # traveling close together are still preserved.
    if (
        payload.session_id is not None
        and payload.source_time_seconds is not None
        and payload.crossing_x is not None
        and payload.crossing_y is not None
    ):
        # V0.5.51: source crossing order can differ from delivery order after
        # interpolation, lost-track finalization or a deferred human guard.
        # Search both sides of the source timestamp; the physical duplicate
        # rules below keep their existing time and distance requirements.
        lookback = max(
            DIRECT_SECONDARY_SHADOW_LOOKBACK_SECONDS, SEMANTIC_FAMILY_SHADOW_LOOKBACK_SECONDS
        )
        lower = max(0.0, float(payload.source_time_seconds) - lookback)
        upper = float(payload.source_time_seconds) + lookback
        family = _vehicle_family_value(payload.vehicle_type)
        family_labels = (
            ("bicycle", "motorcycle") if family == "two-wheel"
            else ("car", "bus", "truck") if family == "four-wheel"
            else (str(getattr(payload.vehicle_type, "value", payload.vehicle_type)),)
        )
        # All current signatures fit inside this 0.050 coordinate envelope.
        # Filtering before iteration avoids an arbitrary 12-row cutoff hiding
        # the true shadow behind newer, spatially unrelated traffic.
        recent = list(db.scalars(select(VehicleEvent).where(
            VehicleEvent.session_id == payload.session_id,
            VehicleEvent.vehicle_type.in_(family_labels),
            VehicleEvent.source_time_seconds.is_not(None),
            VehicleEvent.source_time_seconds >= lower,
            VehicleEvent.source_time_seconds <= upper,
            VehicleEvent.crossing_x >= float(payload.crossing_x) - 0.050,
            VehicleEvent.crossing_x <= float(payload.crossing_x) + 0.050,
            VehicleEvent.crossing_y >= float(payload.crossing_y) - 0.050,
            VehicleEvent.crossing_y <= float(payload.crossing_y) + 0.050,
        ).order_by(VehicleEvent.id.desc())).all())
        for other in recent:
            if other.crossing_x is None or other.crossing_y is None:
                continue
            if payload.tracking_id is not None and other.tracking_id == payload.tracking_id:
                continue
            if _vehicle_family_value(other.vehicle_type) != _vehicle_family_value(payload.vehicle_type):
                continue
            dx = float(payload.crossing_x) - float(other.crossing_x)
            dy = float(payload.crossing_y) - float(other.crossing_y)
            distance = (dx * dx + dy * dy) ** 0.5
            time_delta = abs(float(payload.source_time_seconds) - float(other.source_time_seconds or 0.0))
            same_direction_pair = str(getattr(other.direction, "value", other.direction)) == str(
                getattr(payload.direction, "value", payload.direction)
            )
            same_class_pair = str(getattr(other.vehicle_type, "value", other.vehicle_type)) == str(
                getattr(payload.vehicle_type, "value", payload.vehicle_type)
            )

            # V0.5.46: cross-ID reverse shadows are considered only when one
            # event is secondary and the crossing point is ultra-close.  The
            # direct/direct opposite-direction case is intentionally preserved.
            if not same_direction_pair:
                if _semantic_family_shadow_duplicate(
                    time_delta, distance, payload.crossing_method, other.crossing_method,
                    same_direction=False, same_class=same_class_pair,
                ):
                    response.headers["X-TrafficAI-Deduplicated"] = "1"
                    response.headers["X-TrafficAI-Dedup-Reason"] = "semantic-family-reverse-shadow"
                    return other
                if (
                    same_class_pair
                    and _secondary_reverse_shadow_duplicate(
                        time_delta, distance, payload.crossing_method, other.crossing_method
                    )
                ):
                    response.headers["X-TrafficAI-Deduplicated"] = "1"
                    response.headers["X-TrafficAI-Dedup-Reason"] = "secondary-reverse-shadow"
                    return other
                continue

            # V0.5.31 startup ghost pair guard. Local video can legitimately start
            # with one vehicle already straddling the gate; tracker/bootstrap may
            # briefly expose two raw IDs for that same object. Suppress only an
            # extremely-near same-direction/same-family pair inside the first
            # second, leaving spatially distinct simultaneous vehicles intact.
            startup_pair = _startup_crossing_signature_duplicate(
                float(payload.source_time_seconds),
                float(other.source_time_seconds or 0.0),
                distance,
            )
            if startup_pair:
                response.headers["X-TrafficAI-Deduplicated"] = "1"
                response.headers["X-TrafficAI-Dedup-Reason"] = "startup-crossing-signature"
                return other

            if time_delta <= 0.22 and distance <= 0.025:
                response.headers["X-TrafficAI-Deduplicated"] = "1"
                response.headers["X-TrafficAI-Dedup-Reason"] = "crossing-signature"
                return other

            # V0.5.50 Semantic Shadow Closure 9.6: preserve exact-class dense
            # traffic, but collapse an ultra-spatial same-family class wobble
            # after an ID switch.  This is especially important for
            # MOTORCYCLE <-> BICYCLE and CAR <-> TRUCK rediscovery.
            if _semantic_family_shadow_duplicate(
                time_delta, distance, payload.crossing_method, other.crossing_method,
                same_direction=True, same_class=same_class_pair,
            ):
                response.headers["X-TrafficAI-Deduplicated"] = "1"
                response.headers["X-TrafficAI-Dedup-Reason"] = "semantic-family-shadow"
                return other

            # V0.5.48 Benchmark Closure 9.4: the generic 0.22 s signature
            # intentionally left direct/direct traffic untouched. Benchmark #30
            # still exposes a tiny same-class/same-direction tail at essentially
            # the same physical crossing point. Collapse only this ultra-spatial
            # direct shadow; all wider direct/direct pairs remain distinct.
            if (
                str(getattr(other.vehicle_type, "value", other.vehicle_type))
                == str(getattr(payload.vehicle_type, "value", payload.vehicle_type))
                and _direct_ultra_spatial_shadow_duplicate(
                    time_delta, distance, payload.crossing_method, other.crossing_method
                )
            ):
                response.headers["X-TrafficAI-Deduplicated"] = "1"
                response.headers["X-TrafficAI-Dedup-Reason"] = "direct-ultra-shadow"
                return other

            # V0.5.49: a direct event can be rediscovered shortly afterwards by
            # an interpolated/rescued branch under a new canonical/raw lineage.
            # Exact class + same direction are already required by this branch;
            # use an ultra-tight point radius and never collapse direct/direct.
            if (
                str(getattr(other.vehicle_type, "value", other.vehicle_type))
                == str(getattr(payload.vehicle_type, "value", payload.vehicle_type))
                and _direct_secondary_shadow_duplicate(
                    time_delta, distance, payload.crossing_method, other.crossing_method
                )
            ):
                response.headers["X-TrafficAI-Deduplicated"] = "1"
                response.headers["X-TrafficAI-Dedup-Reason"] = "direct-secondary-shadow"
                return other

            # V0.5.45: close the narrow secondary-shadow gap exposed by
            # Benchmark #26. Exact class match + ultra-close crossing point are
            # required; direct/direct dense traffic is never widened.
            if (
                str(getattr(other.vehicle_type, "value", other.vehicle_type))
                == str(getattr(payload.vehicle_type, "value", payload.vehicle_type))
                and _secondary_shadow_signature_duplicate(
                    time_delta, distance, payload.crossing_method, other.crossing_method
                )
            ):
                response.headers["X-TrafficAI-Deduplicated"] = "1"
                response.headers["X-TrafficAI-Dedup-Reason"] = "secondary-shadow-signature"
                return other

            # V0.5.35: secondary two-wheel center/gap rescue can rediscover the
            # same physical crossing under a new ByteTrack ID. Widen only when
            # at least one event came from a secondary crossing method, and use
            # a tighter crossing-point distance than the generic guard.
            if (
                _vehicle_family_value(other.vehicle_type) == "two-wheel"
                and _vehicle_family_value(payload.vehicle_type) == "two-wheel"
                and _two_wheel_spatial_signature_duplicate(
                    time_delta, distance, payload.crossing_method, other.crossing_method
                )
            ):
                response.headers["X-TrafficAI-Deduplicated"] = "1"
                response.headers["X-TrafficAI-Dedup-Reason"] = "two-wheel-spatial-signature"
                return other

            # V0.5.38: one final tail for benchmark-proven same-point
            # duplicates that fall just beyond the V0.5.37 0.75 s window.  Space
            # is tightened to <= 0.008 and direct/direct remains forbidden.
            if (
                _vehicle_family_value(other.vehicle_type) == "two-wheel"
                and _vehicle_family_value(payload.vehicle_type) == "two-wheel"
                and _two_wheel_ultra_spatial_signature_duplicate(
                    time_delta, distance, payload.crossing_method, other.crossing_method
                )
            ):
                response.headers["X-TrafficAI-Deduplicated"] = "1"
                response.headers["X-TrafficAI-Dedup-Reason"] = "two-wheel-ultra-spatial-signature"
                return other

            # V0.5.30 four-wheel semantic signature: one van can cross while
            # its class flips CAR <-> TRUCK and ByteTrack changes raw ID. The
            # generic 0.22 s signature is intentionally tight for motorcycles;
            # use a slightly wider window only for a cross-class four-wheel pair.
            # This suppresses a duplicate semantic event without penalising two
            # motorcycles or two normal cars following each other closely.
            if _cross_class_heavy_signature_duplicate(
                time_delta, distance, payload.vehicle_type, other.vehicle_type
            ):
                response.headers["X-TrafficAI-Deduplicated"] = "1"
                response.headers["X-TrafficAI-Dedup-Reason"] = "heavy-semantic-signature"
                return other

    response.headers["X-TrafficAI-Deduplicated"] = "0"
    event = VehicleEvent(**payload.model_dump(exclude_none=True))
    db.add(event)
    if session is not None:
        _sync_session_persisted_total(session, int(session.total_vehicles or 0) + 1)

    now = datetime.now(timezone.utc)
    period_start = now.replace(minute=0, second=0, microsecond=0)
    period_end = period_start + timedelta(hours=1)
    bucket = db.scalar(select(VehicleCount).where(
        VehicleCount.camera_id == payload.camera_id,
        VehicleCount.vehicle_type == payload.vehicle_type,
        VehicleCount.direction == payload.direction,
        VehicleCount.period_start == period_start,
    ).execution_options(populate_existing=True))
    if bucket is None:
        bucket = VehicleCount(
            camera_id=payload.camera_id,
            vehicle_type=payload.vehicle_type,
            direction=payload.direction,
            count=1,
            period_start=period_start,
            period_end=period_end,
        )
        db.add(bucket)
    else:
        bucket.count += 1

    db.commit()
    db.refresh(event)
    return event


@router.post("/internal/sessions/{session_id}/finish")
def internal_session_finish(session_id: int, payload: SessionFinish, x_ai_token: str | None = Header(default=None), db: Session = Depends(get_db)) -> dict:
    _assert_ai_token(x_ai_token)
    initial_session = db.get(CountingSession, session_id)
    if initial_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    camera = db.scalar(select(Camera).where(
        Camera.id == initial_session.camera_id,
    ).with_for_update().execution_options(populate_existing=True))
    session = db.scalar(select(CountingSession).where(
        CountingSession.id == session_id,
    ).with_for_update().execution_options(populate_existing=True))
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    persisted_events = list(db.scalars(select(VehicleEvent).where(VehicleEvent.session_id == session_id).order_by(VehicleEvent.id)).all())
    persisted_count = len(persisted_events)
    persisted_in = sum(1 for event in persisted_events if str(getattr(event.direction, "value", event.direction)) == "in")
    persisted_out = sum(1 for event in persisted_events if str(getattr(event.direction, "value", event.direction)) == "out")
    persisted_by_type = {name: 0 for name in ("motorcycle", "bicycle", "car", "bus", "truck", "other")}
    for event in persisted_events:
        label = str(getattr(event.vehicle_type, "value", event.vehicle_type))
        persisted_by_type[label if label in persisted_by_type else "other"] += 1
    session.worker_total_vehicles = int(payload.total_vehicles)
    _sync_session_persisted_total(session, persisted_count)
    session.human_guard_rejections = max(0, int(payload.human_guard_rejections or 0))
    session.average_fps = payload.average_fps
    if payload.source_fps is not None:
        session.source_fps = payload.source_fps
    if payload.source_duration_seconds is not None:
        session.source_duration_seconds = payload.source_duration_seconds
    if session.ended_at is None:
        session.ended_at = datetime.now(timezone.utc)
    session.status = SessionStatus.error if payload.status == "error" else (SessionStatus.completed if payload.status == "completed" else SessionStatus.stopped)
    latest_session = db.scalar(select(CountingSession).where(
        CountingSession.camera_id == session.camera_id,
    ).order_by(CountingSession.id.desc()))
    if camera and _session_finish_owns_camera(session, latest_session):
        camera.status = CameraStatus.error if payload.status == "error" else CameraStatus.inactive
    db.commit()
    return {
        "status": "ok",
        "worker_total_vehicles": int(payload.total_vehicles),
        "persisted_events": persisted_count,
        "persisted_in": persisted_in,
        "persisted_out": persisted_out,
        "persisted_by_type": persisted_by_type,
        "dedup_suppressed_events": session.dedup_suppressed_events,
        "human_guard_rejections": session.human_guard_rejections,
    }


@router.get("/benchmarks")
def list_benchmarks(
    camera_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = select(CountingBenchmark)
    if camera_id is not None:
        stmt = stmt.where(CountingBenchmark.camera_id == camera_id)
    rows = list(db.scalars(stmt.order_by(CountingBenchmark.id.desc()).limit(limit)).all())
    result = []
    for row in rows:
        count = db.scalar(select(func.count(GroundTruthCrossing.id)).where(GroundTruthCrossing.benchmark_id == row.id)) or 0
        result.append(_benchmark_payload(row, int(count)))
    return result


@router.post("/benchmarks", status_code=201)
def create_benchmark(payload: BenchmarkCreate, db: Session = Depends(get_db)) -> dict:
    session = db.get(CountingSession, payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên đếm để benchmark.")
    camera = db.get(Camera, session.camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera của phiên đếm không còn tồn tại.")
    source_url = session.source_url or camera.source_url
    if not source_url:
        raise HTTPException(status_code=422, detail="Phiên đếm không có nguồn video để tạo ground truth.")
    tolerance = min(3.0, max(0.05, float(payload.tolerance_seconds)))
    source_fps = session.source_fps
    source_duration = session.source_duration_seconds
    if camera.source_type.value == "video" and (not source_fps or not source_duration):
        try:
            response = httpx.post(
                f"{settings.ai_service_url}/sources/validate",
                params={"probe": "true"},
                json={"source_type": "video", "source_url": source_url},
                timeout=8.0,
            )
            if response.is_success:
                metadata = response.json()
                source_fps = source_fps or metadata.get("fps")
                source_duration = source_duration or metadata.get("duration_seconds")
        except Exception:
            pass
    name = (payload.name or f"Benchmark Session #{session.id}").strip()[:180]
    row = CountingBenchmark(
        camera_id=session.camera_id,
        session_id=session.id,
        name=name,
        source_url=source_url,
        source_fps=source_fps,
        source_duration_seconds=source_duration,
        line_x1=camera.line_x1, line_y1=camera.line_y1,
        line_x2=camera.line_x2, line_y2=camera.line_y2,
        road_x1=camera.road_x1, road_y1=camera.road_y1,
        road_x2=camera.road_x2, road_y2=camera.road_y2,
        road_x3=camera.road_x3, road_y3=camera.road_y3,
        road_x4=camera.road_x4, road_y4=camera.road_y4,
        tolerance_seconds=tolerance,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    cloned_marks = 0
    if payload.clone_marks_from_benchmark_id is not None:
        source_benchmark = db.get(CountingBenchmark, payload.clone_marks_from_benchmark_id)
        if source_benchmark is None:
            db.delete(row); db.commit()
            raise HTTPException(status_code=404, detail="Benchmark nguồn để sao chép Ground Truth không tồn tại.")
        same_source = source_benchmark.source_url == row.source_url
        line_delta = max(
            abs(source_benchmark.line_x1 - row.line_x1), abs(source_benchmark.line_y1 - row.line_y1),
            abs(source_benchmark.line_x2 - row.line_x2), abs(source_benchmark.line_y2 - row.line_y2),
        )
        if not same_source or line_delta > 0.002:
            db.delete(row); db.commit()
            raise HTTPException(
                status_code=422,
                detail="Không thể sao chép GT: session mới phải dùng đúng video và đúng vạch đếm của benchmark nguồn.",
            )
        source_marks = list(db.scalars(
            select(GroundTruthCrossing)
            .where(GroundTruthCrossing.benchmark_id == source_benchmark.id)
            .order_by(GroundTruthCrossing.source_time_seconds, GroundTruthCrossing.id)
        ).all())
        for mark in source_marks:
            db.add(GroundTruthCrossing(
                benchmark_id=row.id,
                source_time_seconds=mark.source_time_seconds,
                source_frame_index=mark.source_frame_index,
                vehicle_type=mark.vehicle_type,
                direction=mark.direction,
                note=mark.note,
            ))
        cloned_marks = len(source_marks)
        db.commit()

    payload_out = _benchmark_payload(row, cloned_marks)
    payload_out["cloned_marks"] = cloned_marks
    return payload_out


def _benchmark_clone_compatibility(source: CountingBenchmark, target: CountingBenchmark) -> tuple[bool, str]:
    if source.id == target.id:
        return False, "Benchmark nguồn và đích phải khác nhau."
    if source.source_url != target.source_url:
        return False, "Không thể sao chép GT: benchmark nguồn và đích phải dùng đúng cùng video."
    line_delta = max(
        abs(source.line_x1 - target.line_x1), abs(source.line_y1 - target.line_y1),
        abs(source.line_x2 - target.line_x2), abs(source.line_y2 - target.line_y2),
    )
    if line_delta > 0.002:
        return False, "Không thể sao chép GT: benchmark nguồn và đích phải dùng đúng cùng vạch đếm."
    return True, "ok"


def _clone_marks_into_existing_benchmark(db: Session, source: CountingBenchmark, target: CountingBenchmark) -> int:
    ok, reason = _benchmark_clone_compatibility(source, target)
    if not ok:
        raise HTTPException(status_code=422, detail=reason)
    existing = db.scalar(
        select(func.count(GroundTruthCrossing.id)).where(GroundTruthCrossing.benchmark_id == target.id)
    ) or 0
    if int(existing) > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Benchmark đích đã có {int(existing)} Ground Truth. Không sao chép chồng để tránh nhân đôi dữ liệu.",
        )
    source_marks = list(db.scalars(
        select(GroundTruthCrossing)
        .where(GroundTruthCrossing.benchmark_id == source.id)
        .order_by(GroundTruthCrossing.source_time_seconds, GroundTruthCrossing.id)
    ).all())
    if not source_marks:
        raise HTTPException(status_code=422, detail="Benchmark nguồn chưa có Ground Truth để sao chép.")
    for mark in source_marks:
        db.add(GroundTruthCrossing(
            benchmark_id=target.id,
            source_time_seconds=mark.source_time_seconds,
            source_frame_index=mark.source_frame_index,
            vehicle_type=mark.vehicle_type,
            direction=mark.direction,
            note=mark.note,
        ))
    db.commit()
    return len(source_marks)


@router.post("/benchmarks/{benchmark_id}/clone-marks")
def clone_benchmark_marks(benchmark_id: int, payload: BenchmarkCloneMarks, db: Session = Depends(get_db)) -> dict:
    target = db.get(CountingBenchmark, benchmark_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Benchmark đích không tồn tại.")
    source = db.get(CountingBenchmark, payload.source_benchmark_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Benchmark nguồn không tồn tại.")
    cloned = _clone_marks_into_existing_benchmark(db, source, target)
    count = db.scalar(
        select(func.count(GroundTruthCrossing.id)).where(GroundTruthCrossing.benchmark_id == target.id)
    ) or 0
    result = _benchmark_payload(target, int(count))
    result["cloned_marks"] = cloned
    result["source_benchmark_id"] = source.id
    return result


@router.get("/benchmarks/{benchmark_id}")
def get_benchmark(benchmark_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(CountingBenchmark, benchmark_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    marks = list(db.scalars(
        select(GroundTruthCrossing)
        .where(GroundTruthCrossing.benchmark_id == benchmark_id)
        .order_by(GroundTruthCrossing.source_time_seconds, GroundTruthCrossing.id)
    ).all())
    payload = _benchmark_payload(row, len(marks))
    payload["marks"] = [_ground_truth_payload(mark) for mark in marks]
    return payload


@router.patch("/benchmarks/{benchmark_id}")
def update_benchmark(benchmark_id: int, payload: BenchmarkUpdate, db: Session = Depends(get_db)) -> dict:
    row = db.get(CountingBenchmark, benchmark_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    row.tolerance_seconds = min(3.0, max(0.05, float(payload.tolerance_seconds)))
    db.commit()
    db.refresh(row)
    count = db.scalar(select(func.count(GroundTruthCrossing.id)).where(GroundTruthCrossing.benchmark_id == row.id)) or 0
    return _benchmark_payload(row, int(count))


@router.delete("/benchmarks/{benchmark_id}")
def delete_benchmark(benchmark_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(CountingBenchmark, benchmark_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    db.delete(row)
    db.commit()
    return {"status": "deleted", "benchmark_id": benchmark_id}


@router.post("/benchmarks/{benchmark_id}/marks", status_code=201)
def create_ground_truth_mark(benchmark_id: int, payload: GroundTruthMarkCreate, db: Session = Depends(get_db)) -> dict:
    benchmark = db.get(CountingBenchmark, benchmark_id)
    if benchmark is None:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    time_seconds = max(0.0, float(payload.source_time_seconds))
    frame_index = None
    if benchmark.source_fps and benchmark.source_fps > 0:
        frame_index = max(1, int(round(time_seconds * benchmark.source_fps)) + 1)
    mark = GroundTruthCrossing(
        benchmark_id=benchmark_id,
        source_time_seconds=time_seconds,
        source_frame_index=frame_index,
        vehicle_type=payload.vehicle_type.value,
        direction=payload.direction.value,
        note=(payload.note or "").strip()[:255] or None,
    )
    db.add(mark)
    db.commit()
    db.refresh(mark)
    return _ground_truth_payload(mark)


@router.patch("/benchmarks/{benchmark_id}/marks/{mark_id}")
def update_ground_truth_mark(benchmark_id: int, mark_id: int, payload: GroundTruthMarkUpdate, db: Session = Depends(get_db)) -> dict:
    """Correct GT class/direction in place without changing its reviewed timecode."""
    mark = db.get(GroundTruthCrossing, mark_id)
    if mark is None or mark.benchmark_id != benchmark_id:
        raise HTTPException(status_code=404, detail="Ground-truth mark not found")
    if payload.vehicle_type is not None:
        mark.vehicle_type = payload.vehicle_type.value
    if payload.direction is not None:
        mark.direction = payload.direction.value
    if payload.note is not None:
        mark.note = payload.note.strip()[:255] or None
    db.commit()
    db.refresh(mark)
    return _ground_truth_payload(mark)


@router.delete("/benchmarks/{benchmark_id}/marks/{mark_id}")
def delete_ground_truth_mark(benchmark_id: int, mark_id: int, db: Session = Depends(get_db)) -> dict:
    mark = db.get(GroundTruthCrossing, mark_id)
    if mark is None or mark.benchmark_id != benchmark_id:
        raise HTTPException(status_code=404, detail="Ground-truth mark not found")
    db.delete(mark)
    db.commit()
    return {"status": "deleted", "mark_id": mark_id}


def _benchmark_trace_targets(report: dict, timed_events: list[VehicleEvent]) -> list[tuple[dict, float]]:
    """Diagnose semantic errors at the AI crossing's actual source position."""
    targets = [(item, float(item["time"])) for item in report["missed_items"]]
    event_by_id = {int(event.id): event for event in timed_events}
    for item in report["class_mismatch_items"]:
        event = event_by_id.get(int(item["ai_event_id"]))
        source_time = getattr(event, "source_time_seconds", None)
        if source_time is None:
            source_time = item.get("ai_time", item["time"])
        item["ai_tracking_id"] = getattr(event, "tracking_id", item.get("tracking_id"))
        targets.append((item, float(source_time)))
    return targets


def _attach_benchmark_trace_diagnosis(item: dict, diagnosis: dict) -> None:
    """Keep class evidence scoped to the matched canonical event track."""
    attached = dict(diagnosis)
    tracking_id = item.get("ai_tracking_id")
    attached["bicycle_context_scope"] = "matched_track" if tracking_id is not None else "nearby_tracks"
    if tracking_id is not None:
        def same_track_audits(audits: list[dict]) -> list[dict]:
            return [audit for audit in audits if audit.get("track_id") == tracking_id]

        if "bicycle_context_audit" in attached:
            attached["bicycle_context_audit"] = same_track_audits(attached["bicycle_context_audit"] or [])
        if isinstance(attached.get("gate_span_audit"), dict):
            span = dict(attached["gate_span_audit"])
            if "bicycle_context_audit" in span:
                span["bicycle_context_audit"] = same_track_audits(span["bicycle_context_audit"] or [])
            attached["gate_span_audit"] = span
    item["diagnosis"] = attached


def _build_benchmark_report(
    benchmark_id: int, db: Session, *,
    source_marks: list[GroundTruthCrossing] | None = None,
    source_events: list[VehicleEvent] | None = None,
) -> dict:
    benchmark = db.get(CountingBenchmark, benchmark_id)
    if benchmark is None:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    marks = source_marks if source_marks is not None else list(db.scalars(
        select(GroundTruthCrossing)
        .where(GroundTruthCrossing.benchmark_id == benchmark_id)
        .order_by(GroundTruthCrossing.source_time_seconds, GroundTruthCrossing.id)
    ).all())
    all_events = source_events if source_events is not None else list(db.scalars(
        select(VehicleEvent)
        .where(VehicleEvent.session_id == benchmark.session_id)
        .order_by(VehicleEvent.id)
    ).all())
    timed_events = [event for event in all_events if event.source_time_seconds is not None]
    report = match_crossings(marks, timed_events, benchmark.tolerance_seconds)
    trace_available = False
    trace_targets = _benchmark_trace_targets(report, timed_events)
    if trace_targets:
        try:
            response = httpx.post(
                f"{settings.ai_service_url}/benchmark-traces/{benchmark.session_id}/diagnose",
                json={
                    "times": [source_time for _, source_time in trace_targets],
                    "tracking_ids": [item.get("ai_tracking_id") for item, _ in trace_targets],
                    "window_seconds": min(1.0, max(0.35, benchmark.tolerance_seconds)),
                },
                timeout=8.0,
            )
            if response.is_success:
                trace = response.json()
                trace_available = bool(trace.get("available"))
                for (item, _), diagnosis in zip(trace_targets, trace.get("items", [])):
                    _attach_benchmark_trace_diagnosis(item, diagnosis)
        except Exception:
            trace_available = False
    miss_reason_counts: dict[str, int] = {}
    for item in report["missed_items"]:
        reason = (item.get("diagnosis") or {}).get("reason")
        if reason:
            miss_reason_counts[reason] = miss_reason_counts.get(reason, 0) + 1
    dominant_miss_reason = max(miss_reason_counts, key=miss_reason_counts.get) if miss_reason_counts else None
    session = db.get(CountingSession, benchmark.session_id)
    persisted_count = len(all_events)
    timed_count = len(timed_events)
    session_total = int(session.total_vehicles) if session is not None else persisted_count
    worker_total = int(session.worker_total_vehicles) if session is not None and session.worker_total_vehicles is not None else session_total
    integrity = {
        "ok": session_total == persisted_count == timed_count,
        "session_total": session_total,
        "worker_total": worker_total,
        "persisted_events": persisted_count,
        "timed_events": timed_count,
        "missing_timecode": persisted_count - timed_count,
        "dedup_suppressed_events": int(session.dedup_suppressed_events) if session is not None else max(0, worker_total - persisted_count),
        "human_guard_rejections": int(session.human_guard_rejections) if session is not None else 0,
    }
    report.update({
        "benchmark": _benchmark_payload(benchmark, len(marks)),
        "session_id": benchmark.session_id,
        "timed_ai_events": timed_count,
        "legacy_ai_events_without_source_time": persisted_count - timed_count,
        "integrity": integrity,
        "trace_available": trace_available,
        "miss_reason_counts": miss_reason_counts,
        "dominant_miss_reason": dominant_miss_reason,
        "ready": bool(marks) and len(timed_events) > 0,
    })
    return report


@router.get("/benchmarks/{benchmark_id}/report")
def benchmark_report(benchmark_id: int, db: Session = Depends(get_db)) -> dict:
    return _build_benchmark_report(benchmark_id, db)


def _benchmark_export_metadata(session: CountingSession | None, camera: Camera | None, model: AIModel | None, benchmark: dict) -> tuple[dict, dict]:
    """Whitelist diagnostics fields; never serialize settings or an ORM object."""
    session_fields = (
        "id", "camera_id", "model_id", "started_at", "ended_at", "status",
        "total_vehicles", "worker_total_vehicles", "dedup_suppressed_events",
        "human_guard_rejections", "average_fps", "source_url", "source_fps",
        "source_duration_seconds",
    )
    session_payload = {field: getattr(session, field, None) for field in session_fields} if session is not None else {"available": False}
    camera_fields = ("id", "source_type", "confidence_threshold")
    current_camera = {field: getattr(camera, field, None) for field in camera_fields} if camera is not None else None
    if current_camera is not None:
        current_camera["geometry"] = {
            field: getattr(camera, field, None) for field in benchmark["geometry"]
        }
    config_payload = {
        "benchmark_snapshot": {
            "geometry": benchmark["geometry"],
            "tolerance_seconds": benchmark["tolerance_seconds"],
        },
        "current_camera": current_camera,
        "session_model": {
            field: getattr(model, field, None) for field in ("id", "name", "version", "architecture")
        } if model is not None else None,
        "inference_settings": "Not stored historically; current environment settings are not substituted.",
    }
    return session_payload, config_payload


def _fetch_benchmark_export_trace(session_id: int) -> tuple[bytes | BenchmarkTraceArchive | None, str]:
    """Optional trace failures leave a usable report ZIP with their status."""
    try:
        deadline = time.monotonic() + 20.0
        for encoding, endpoint in (("gzip", "download-gzip"), ("identity", "download")):
            if time.monotonic() > deadline:
                raise TimeoutError("Benchmark trace download timed out")
            with httpx.stream(
                "GET", f"{settings.ai_service_url}/benchmark-traces/{int(session_id)}/{endpoint}",
                timeout=8.0, follow_redirects=False,
            ) as response:
                if response.status_code == 404:
                    if encoding == "gzip":
                        continue  # Legacy service or no certified closed gzip yet.
                    return None, "not_found"
                if not response.is_success:
                    return None, f"http_error_{response.status_code}"
                # Never let HTTP automatic content decoding expand gzip before
                # the transport cap; this endpoint serves application/gzip.
                if encoding == "gzip" and response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    return None, "invalid_metadata"
                try:
                    announced_bytes = int(response.headers.get("Content-Length", "0"))
                except (TypeError, ValueError):
                    announced_bytes = 0
                if announced_bytes > BENCHMARK_TRACE_EXPORT_MAX_BYTES:
                    return None, "too_large"

                def chunks():
                    for chunk in response.iter_bytes(chunk_size=64 * 1024):
                        if time.monotonic() > deadline:
                            raise TimeoutError("Benchmark trace download timed out")
                        yield chunk

                trace = read_benchmark_trace_chunks(chunks(), max_bytes=BENCHMARK_TRACE_EXPORT_MAX_BYTES)
                if time.monotonic() > deadline:
                    raise TimeoutError("Benchmark trace download timed out")
                if announced_bytes > 0 and len(trace) != announced_bytes:
                    return None, "incomplete"
                if not trace:
                    return None, "empty"
                if encoding == "identity":
                    return trace, "available"
                try:
                    source_bytes = int(response.headers.get("X-Traffic-AI-Trace-Source-Bytes", "-1"))
                    source_sha256 = response.headers.get("X-Traffic-AI-Trace-Source-SHA256", "")
                    compressed_sha256 = response.headers.get("X-Traffic-AI-Trace-Compressed-SHA256", "")
                    from hashlib import sha256
                    if (response.headers.get("X-Traffic-AI-Trace-Closed") != "true"
                            or source_bytes < 0 or not re.fullmatch(r"[0-9a-f]{64}", source_sha256)
                            or not re.fullmatch(r"[0-9a-f]{64}", compressed_sha256)
                            or not trace.startswith(b"\x1f\x8b") or sha256(trace).hexdigest() != compressed_sha256):
                        return None, "invalid_metadata"
                except (TypeError, ValueError):
                    return None, "invalid_metadata"
                if source_bytes == 0:
                    return None, "empty"
                if time.monotonic() > deadline:
                    raise TimeoutError("Benchmark trace download timed out")
                return BenchmarkTraceArchive(trace, source_bytes, source_sha256, compressed_sha256), "available"
    except BenchmarkTraceTooLarge:
        return None, "too_large"
    except (httpx.TimeoutException, TimeoutError):
        return None, "timeout"
    except Exception:
        # Exception messages may contain a service URL, so they are not copied
        # into a shareable archive. Database/report failures are not caught here.
        return None, "service_unavailable"


@router.get("/benchmarks/{benchmark_id}/export")
def export_benchmark(benchmark_id: int, db: Session = Depends(get_db)) -> Response:
    benchmark = db.get(CountingBenchmark, benchmark_id)
    if benchmark is None:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    marks = list(db.scalars(select(GroundTruthCrossing).where(
        GroundTruthCrossing.benchmark_id == benchmark_id,
    ).order_by(GroundTruthCrossing.source_time_seconds, GroundTruthCrossing.id)).all())
    events = list(db.scalars(select(VehicleEvent).where(
        VehicleEvent.session_id == benchmark.session_id,
    ).order_by(VehicleEvent.id)).all())
    report = _build_benchmark_report(benchmark_id, db, source_marks=marks, source_events=events)
    session = db.get(CountingSession, benchmark.session_id)
    camera = db.get(Camera, benchmark.camera_id)
    model = db.get(AIModel, session.model_id) if session is not None and session.model_id is not None else None
    session_payload, config_payload = _benchmark_export_metadata(session, camera, model, report["benchmark"])
    event_fields = (
        "id", "camera_id", "session_id", "model_id", "tracking_id", "vehicle_type",
        "direction", "confidence", "detected_at", "source_frame_index",
        "source_time_seconds", "crossing_method", "crossing_x", "crossing_y",
    )
    event_payloads = [{field: getattr(event, field, None) for field in event_fields} for event in events]
    trace, trace_reason = _fetch_benchmark_export_trace(benchmark.session_id)
    archive = build_benchmark_export(
        report=report, marks=[_ground_truth_payload(mark) for mark in marks], events=event_payloads,
        session=session_payload, config=config_payload, exported_at=datetime.now(timezone.utc),
        trace=trace, trace_reason=trace_reason,
    )
    return Response(
        archive, media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="traffic-ai-benchmark-{benchmark.id}-session-{benchmark.session_id}.zip"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/benchmarks/{benchmark_id}/reconcile")
def reconcile_benchmark(benchmark_id: int, db: Session = Depends(get_db)) -> dict:
    """Force a fresh GT↔AI reconciliation and return an explicit timestamp.

    V0.5.21 makes the UI action observable instead of silently issuing the same
    GET again. The report is always rebuilt from current GT marks and persisted
    vehicle events; nothing is cached or mutated by this endpoint.
    """
    report = _build_benchmark_report(benchmark_id, db)
    report["reconciled_at"] = datetime.now(timezone.utc).isoformat()
    report["recomputed"] = True
    return report


@router.get("/meta/vehicle-types")
def vehicle_types() -> list[str]:
    return [item.value for item in VehicleType]


@router.get("/meta/directions")
def directions() -> list[str]:
    return [item.value for item in Direction]


@router.get("/datasets")
def list_datasets(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(DatasetRecord).order_by(DatasetRecord.id.desc())).all()
    return [_dataset_payload(row) for row in rows]


@router.post("/datasets", status_code=201)
def create_dataset(payload: DatasetCreate, db: Session = Depends(get_db)) -> dict:
    camera = db.get(Camera, payload.camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    if camera.source_type.value != "video":
        raise HTTPException(status_code=422, detail="V0.5.9 trích dataset tự động từ video local trước; RTSP sẽ bổ sung ở bản sau.")
    base_slug = _dataset_slug(payload.name)
    slug = base_slug
    suffix = 1
    while db.scalar(select(DatasetRecord.id).where(DatasetRecord.slug == slug)) is not None:
        suffix += 1
        slug = f"{base_slug}-{suffix}"
    row = DatasetRecord(
        name=payload.name.strip(), slug=slug, source_camera_id=camera.id, source_url=camera.source_url,
        root_path=f"/data/datasets/{slug}", status="extracting", sample_every_n_frames=payload.every_n_frames,
    )
    db.add(row); db.commit(); db.refresh(row)
    try:
        response = httpx.post(f"{settings.ai_service_url}/datasets/extract", json={
            "slug": slug, "source_url": camera.source_url, "every_n_frames": payload.every_n_frames,
            "max_images": payload.max_images,
            "smart_dedupe": payload.smart_dedupe,
            "min_change_ratio": payload.min_change_ratio,
        }, timeout=120.0)
        response.raise_for_status(); info = response.json()
        row.image_count = int(info.get("image_count", 0)); row.status = "extracted"
        db.commit(); db.refresh(row)
    except Exception as exc:
        row.status = "error"; db.commit()
        raise HTTPException(status_code=502, detail=f"Không trích được dataset: {exc}") from exc
    return {**_dataset_payload(row), **{k: info.get(k) for k in ("sampled_candidates", "skipped_similar", "smart_dedupe", "min_change_ratio")}}


@router.post("/datasets/{dataset_id}/autolabel")
def autolabel_dataset(dataset_id: int, payload: DatasetAction, db: Session = Depends(get_db)) -> dict:
    row = db.get(DatasetRecord, dataset_id)
    if row is None: raise HTTPException(status_code=404, detail="Dataset not found")
    model = db.scalar(select(AIModel).where(AIModel.is_active.is_(True)).order_by(AIModel.id.desc()))
    model_path = model.model_path if model else "yolo26s.pt"
    response = httpx.post(f"{settings.ai_service_url}/datasets/autolabel", json={"slug": row.slug, "model_path": model_path, "confidence": payload.confidence}, timeout=3600.0)
    if not response.is_success: raise HTTPException(status_code=502, detail=response.text)
    info = response.json(); row.labeled_images = int(info.get("labeled_images", 0)); row.box_count = int(info.get("box_count", 0)); row.status = "pseudo_labeled"
    db.commit(); db.refresh(row)
    return {**_dataset_payload(row), "warning": "Auto-label chỉ là nhãn gợi ý. Hãy rà soát nhãn trước khi train để tránh học sai."}


@router.get("/datasets/{dataset_id}/stats")
def dataset_stats_route(dataset_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(DatasetRecord, dataset_id)
    if row is None: raise HTTPException(status_code=404, detail="Dataset not found")
    response = httpx.get(f"{settings.ai_service_url}/datasets/{row.slug}/stats", timeout=30.0)
    if not response.is_success: raise HTTPException(status_code=502, detail=response.text)
    return response.json()


@router.get("/datasets/{dataset_id}/annotations")
def list_dataset_annotations(
    dataset_id: int,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
    review_mode: str = Query(default="priority"),
    db: Session = Depends(get_db),
) -> dict:
    row = db.get(DatasetRecord, dataset_id)
    if row is None: raise HTTPException(status_code=404, detail="Dataset not found")
    response = httpx.get(
        f"{settings.ai_service_url}/datasets/{row.slug}/annotations",
        params={"offset": offset, "limit": limit, "review_mode": review_mode},
        timeout=30.0,
    )
    if not response.is_success: raise HTTPException(status_code=502, detail=response.text)
    info = response.json()
    row.reviewed_images = int(info.get("reviewed_images", row.reviewed_images or 0))
    row.difficult_images = int(info.get("difficult_images", row.difficult_images or 0))
    db.commit()
    return info


@router.get("/datasets/{dataset_id}/annotations/{image_name}")
def get_dataset_annotation(dataset_id: int, image_name: str, db: Session = Depends(get_db)) -> dict:
    row = db.get(DatasetRecord, dataset_id)
    if row is None: raise HTTPException(status_code=404, detail="Dataset not found")
    response = httpx.get(f"{settings.ai_service_url}/datasets/{row.slug}/annotations/{image_name}", timeout=30.0)
    if not response.is_success: raise HTTPException(status_code=response.status_code if response.status_code < 500 else 502, detail=response.text)
    return response.json()


@router.get("/datasets/{dataset_id}/images/{image_name}")
def get_dataset_image(dataset_id: int, image_name: str, db: Session = Depends(get_db)) -> Response:
    row = db.get(DatasetRecord, dataset_id)
    if row is None: raise HTTPException(status_code=404, detail="Dataset not found")
    response = httpx.get(f"{settings.ai_service_url}/datasets/{row.slug}/images/{image_name}", timeout=30.0)
    if not response.is_success: raise HTTPException(status_code=response.status_code if response.status_code < 500 else 502, detail=response.text)
    return Response(content=response.content, media_type=response.headers.get("content-type", "image/jpeg"), headers={"Cache-Control": "no-store"})


@router.put("/datasets/{dataset_id}/annotations/{image_name}")
def save_dataset_annotation(dataset_id: int, image_name: str, payload: AnnotationUpdate, db: Session = Depends(get_db)) -> dict:
    row = db.get(DatasetRecord, dataset_id)
    if row is None: raise HTTPException(status_code=404, detail="Dataset not found")
    response = httpx.put(f"{settings.ai_service_url}/datasets/{row.slug}/annotations/{image_name}", json=payload.model_dump(), timeout=30.0)
    if not response.is_success: raise HTTPException(status_code=response.status_code if response.status_code < 500 else 502, detail=response.text)
    info = response.json()
    row.reviewed_images = int(info.get("reviewed_images", row.reviewed_images or 0))
    row.difficult_images = int(info.get("difficult_images", row.difficult_images or 0))
    row.status = "labeled" if row.reviewed_images > 0 else row.status
    # Recompute the dataset counters after manual label edits.
    try:
        stats_response = httpx.get(f"{settings.ai_service_url}/datasets/{row.slug}/stats", timeout=15.0)
        if stats_response.is_success:
            stats = stats_response.json()
            row.labeled_images = int(stats.get("labeled_images", row.labeled_images))
            row.box_count = int(stats.get("box_count", row.box_count))
    except Exception:
        pass
    db.commit(); db.refresh(row)
    return {**info, "dataset": _dataset_payload(row)}


@router.post("/datasets/{dataset_id}/annotations/accept-safe")
def accept_safe_dataset_annotations(dataset_id: int, payload: AnnotationBulkAccept, db: Session = Depends(get_db)) -> dict:
    row = db.get(DatasetRecord, dataset_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    response = httpx.post(
        f"{settings.ai_service_url}/datasets/{row.slug}/annotations/accept-safe",
        json={"min_confidence": payload.min_confidence},
        timeout=60.0,
    )
    if not response.is_success:
        raise HTTPException(status_code=response.status_code if response.status_code < 500 else 502, detail=response.text)
    info = response.json()
    row.reviewed_images = int(info.get("reviewed_images", row.reviewed_images or 0))
    if row.reviewed_images > 0:
        row.status = "labeled"
    db.commit(); db.refresh(row)
    return {**info, "dataset": _dataset_payload(row)}


@router.post("/datasets/{dataset_id}/reset-labels")
def reset_dataset_labels_route(dataset_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(DatasetRecord, dataset_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    running = db.scalar(select(TrainingRun.id).where(TrainingRun.dataset_id == dataset_id, TrainingRun.status.in_(["queued", "running"])))
    if running is not None:
        raise HTTPException(status_code=409, detail="Không thể làm lại nhãn khi training run của dataset đang chạy.")
    response = httpx.post(f"{settings.ai_service_url}/datasets/{row.slug}/reset-labels", timeout=60.0)
    if not response.is_success:
        raise HTTPException(status_code=response.status_code if response.status_code < 500 else 502, detail=response.text)
    info = response.json()
    row.status = "extracted"
    row.labeled_images = 0
    row.box_count = 0
    row.reviewed_images = 0
    row.difficult_images = 0
    row.train_count = 0
    row.val_count = 0
    row.test_count = 0
    db.commit(); db.refresh(row)
    return {**info, "dataset": _dataset_payload(row)}


@router.delete("/datasets/{dataset_id}")
def delete_dataset_route(dataset_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(DatasetRecord, dataset_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    runs = db.scalars(select(TrainingRun).where(TrainingRun.dataset_id == dataset_id).order_by(TrainingRun.id)).all()
    if any(run.status in {"queued", "running"} for run in runs):
        raise HTTPException(status_code=409, detail="Không thể xóa dataset khi training run đang chạy.")
    run_ids = [int(run.id) for run in runs]
    response = httpx.post(
        f"{settings.ai_service_url}/datasets/purge",
        json={"slug": row.slug, "run_ids": run_ids, "purge_training_runs": True},
        timeout=120.0,
    )
    if not response.is_success:
        raise HTTPException(status_code=response.status_code if response.status_code < 500 else 502, detail=response.text)
    info = response.json()
    # Xóa history training của dataset khỏi DB. best.pt đã export trong /data/models được giữ lại.
    for run in runs:
        db.delete(run)
    db.delete(row)
    db.commit()
    return {**info, "dataset_id": dataset_id, "deleted": True}


@router.post("/datasets/{dataset_id}/prepare")
def prepare_dataset_route(dataset_id: int, payload: DatasetAction, db: Session = Depends(get_db)) -> dict:
    row = db.get(DatasetRecord, dataset_id)
    if row is None: raise HTTPException(status_code=404, detail="Dataset not found")
    response = httpx.post(f"{settings.ai_service_url}/datasets/prepare", json={
        "slug": row.slug, "train_ratio": payload.train_ratio, "val_ratio": payload.val_ratio, "seed": payload.seed,
    }, timeout=180.0)
    if not response.is_success: raise HTTPException(status_code=502, detail=response.text)
    info = response.json(); splits = info.get("splits", {})
    row.train_count = int(splits.get("train", 0)); row.val_count = int(splits.get("val", 0)); row.test_count = int(splits.get("test", 0)); row.status = "ready"
    db.commit(); db.refresh(row)
    return {**_dataset_payload(row), "dataset_yaml": info.get("dataset_yaml")}


@router.get("/training/runs")
def list_training_runs(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(TrainingRun).order_by(TrainingRun.id.desc()).limit(50)).all()
    for row in rows:
        if row.status in {"queued", "running"}:
            try:
                response = httpx.get(f"{settings.ai_service_url}/training/{row.id}", timeout=2.0)
                if response.is_success:
                    state = response.json(); row.status = state.get("status", row.status); row.current_epoch = int(state.get("current_epoch", row.current_epoch)); row.progress = float(state.get("progress", row.progress)); row.precision = state.get("precision"); row.recall = state.get("recall"); row.map50 = state.get("map50"); row.map50_95 = state.get("map50_95"); row.best_model_path = state.get("best_model_path"); row.last_error = state.get("last_error")
                    if row.status == "running" and row.started_at is None: row.started_at = datetime.now(timezone.utc)
                    if row.status in {"completed", "failed"} and row.ended_at is None: row.ended_at = datetime.now(timezone.utc)
            except Exception:
                pass
    db.commit()
    active_model = db.scalar(select(AIModel).where(AIModel.is_active.is_(True)).order_by(AIModel.id.desc()))
    payloads = []
    for row in rows:
        payload = _training_payload(row)
        payload["is_active_model"] = bool(active_model and row.best_model_path and active_model.model_path == row.best_model_path)
        payload["active_model_id"] = active_model.id if payload["is_active_model"] else None
        payloads.append(payload)
    return payloads


@router.post("/training/runs", status_code=201)
def create_training_run(payload: TrainingCreate, db: Session = Depends(get_db)) -> dict:
    dataset = db.get(DatasetRecord, payload.dataset_id)
    if dataset is None: raise HTTPException(status_code=404, detail="Dataset not found")
    if dataset.status != "ready": raise HTTPException(status_code=409, detail="Dataset phải ở trạng thái ready trước khi train.")
    row = TrainingRun(dataset_id=dataset.id, base_model=payload.base_model, epochs=payload.epochs, imgsz=payload.imgsz, batch_size=payload.batch, device=payload.device, status="queued")
    db.add(row); db.commit(); db.refresh(row)
    response = httpx.post(f"{settings.ai_service_url}/training/start", json={
        "run_id": row.id, "dataset_slug": dataset.slug, "base_model": row.base_model, "epochs": row.epochs,
        "imgsz": row.imgsz, "batch": row.batch_size, "device": row.device,
    }, timeout=15.0)
    if not response.is_success:
        row.status="failed"; row.last_error=response.text; db.commit(); raise HTTPException(status_code=502, detail=response.text)
    row.status="running"; row.started_at=datetime.now(timezone.utc); db.commit(); db.refresh(row)
    return _training_payload(row)


@router.post("/training/runs/{run_id}/activate")
def activate_training_model(run_id: int, db: Session = Depends(get_db)) -> dict:
    run = db.get(TrainingRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Training run not found")

    # Đồng bộ trạng thái mới nhất trước khi kích hoạt. Nếu AI Service đã restart
    # nhưng DB đã lưu completed + best_model_path thì vẫn cho phép kích hoạt.
    if run.status in {"queued", "running"}:
        list_training_runs(db)
        db.refresh(run)
    if run.status != "completed" or not run.best_model_path:
        raise HTTPException(status_code=409, detail="Training run chưa hoàn tất hoặc chưa có best.pt")

    dataset = db.get(DatasetRecord, run.dataset_id)
    model_name = f"Traffic AI Custom #{run.id}"

    # Idempotent activation: nếu lần bấm trước đã INSERT thành công nhưng client
    # nhận lỗi/proxy timeout, lần bấm lại chỉ kích hoạt bản ghi hiện có thay vì
    # đụng UniqueConstraint(name, version) và trả HTTP 500 text/plain.
    model = db.scalar(select(AIModel).where(AIModel.model_path == run.best_model_path).order_by(AIModel.id.desc()))
    already_active = bool(model and model.is_active)
    try:
        db.query(AIModel).update({AIModel.is_active: False}, synchronize_session=False)
        if model is None:
            model = AIModel(
                name=model_name, version=f"run-{run.id}", architecture="YOLO26",
                model_path=run.best_model_path, training_dataset=dataset.name if dataset else None,
                precision=run.precision, recall=run.recall, map50=run.map50, map50_95=run.map50_95, is_active=True,
            )
            db.add(model)
        else:
            model.name = model_name
            model.training_dataset = dataset.name if dataset else model.training_dataset
            model.precision = run.precision
            model.recall = run.recall
            model.map50 = run.map50
            model.map50_95 = run.map50_95
            model.is_active = True
        db.commit()
        db.refresh(model)
    except IntegrityError:
        db.rollback()
        # Hỗ trợ dữ liệu V0.5.4 đã từng tạo model cùng tên/version trong một
        # lần kích hoạt dở dang. Tìm lại model theo tên, cập nhật path/metrics và
        # kích hoạt thay vì trả Internal Server Error.
        model = db.scalar(select(AIModel).where(AIModel.name == model_name).order_by(AIModel.id.desc()))
        if model is None:
            raise HTTPException(status_code=409, detail="Không thể kích hoạt best.pt do xung đột model trong PostgreSQL")
        db.query(AIModel).update({AIModel.is_active: False}, synchronize_session=False)
        model.model_path = run.best_model_path
        model.training_dataset = dataset.name if dataset else model.training_dataset
        model.precision = run.precision
        model.recall = run.recall
        model.map50 = run.map50
        model.map50_95 = run.map50_95
        model.is_active = True
        db.commit()
        db.refresh(model)

    return {
        "status": "active", "model_id": model.id, "model_path": model.model_path,
        "name": model.name, "already_active": already_active, "run_id": run.id,
    }
