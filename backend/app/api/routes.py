from datetime import datetime, timedelta, timezone

import httpx2 as httpx
import json
import re
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.geometry import validate_counting_geometry
from app.benchmarking import match_crossings
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
    average_fps: float | None = None
    source_fps: float | None = None
    source_duration_seconds: float | None = None
    last_error: str | None = None


class BenchmarkCreate(BaseModel):
    session_id: int
    name: str | None = None
    tolerance_seconds: float = 0.75


class BenchmarkUpdate(BaseModel):
    tolerance_seconds: float


class GroundTruthMarkCreate(BaseModel):
    source_time_seconds: float
    direction: Direction = Direction.unknown
    vehicle_type: VehicleType = VehicleType.motorcycle
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
        "total_vehicles": row.total_vehicles, "average_fps": row.average_fps,
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
                ai_is_running = ai_state.get("status") in {"starting", "warming", "running"}
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
        camera.status = CameraStatus.error
        db.commit()
        raise HTTPException(status_code=502, detail=f"AI service could not start pipeline: {exc}") from exc
    return {"session_id": session.id, "camera_id": camera_id, "source_repaired": source_repaired, "source_url": camera.source_url, "pipeline": response.json()}


@router.post("/cameras/{camera_id}/stop")
def stop_camera(camera_id: int, db: Session = Depends(get_db)) -> dict:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    session = db.scalar(select(CountingSession).where(CountingSession.camera_id == camera_id, CountingSession.status == SessionStatus.running).order_by(CountingSession.id.desc()))
    try:
        response = httpx.post(f"{settings.ai_service_url}/pipelines/{camera_id}/stop", timeout=12.0)
        if response.status_code not in (200, 404):
            response.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI service could not stop pipeline: {exc}") from exc
    if session:
        session.status = SessionStatus.stopped
        session.ended_at = datetime.now(timezone.utc)
    camera.status = CameraStatus.inactive
    db.commit()
    return {"status": "stopped", "camera_id": camera_id}


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


@router.post("/internal/events", response_model=VehicleEventRead, status_code=201)
def internal_event(payload: VehicleEventCreate, x_ai_token: str | None = Header(default=None), db: Session = Depends(get_db)) -> VehicleEvent:
    _assert_ai_token(x_ai_token)

    # Event delivery is retried by the AI service. Make this endpoint idempotent
    # for one ByteTrack ID inside one counting session so a network retry cannot
    # double-count a vehicle.
    existing = None
    if payload.session_id is not None and payload.tracking_id is not None:
        # One ByteTrack ID may legitimately cross the gate once in each direction
        # (two-way traffic / turn-around). Network retries for the same crossing
        # must remain idempotent, so direction is part of the key.
        existing = db.scalar(select(VehicleEvent).where(
            VehicleEvent.session_id == payload.session_id,
            VehicleEvent.tracking_id == payload.tracking_id,
            VehicleEvent.direction == payload.direction,
        ).order_by(VehicleEvent.id.desc()))
    if existing is not None:
        return existing

    event = VehicleEvent(**payload.model_dump(exclude_none=True))
    db.add(event)
    if payload.session_id:
        session = db.get(CountingSession, payload.session_id)
        if session:
            session.total_vehicles += 1

    now = datetime.now(timezone.utc)
    period_start = now.replace(minute=0, second=0, microsecond=0)
    period_end = period_start + timedelta(hours=1)
    bucket = db.scalar(select(VehicleCount).where(
        VehicleCount.camera_id == payload.camera_id,
        VehicleCount.vehicle_type == payload.vehicle_type,
        VehicleCount.direction == payload.direction,
        VehicleCount.period_start == period_start,
    ))
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
    session = db.get(CountingSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    session.total_vehicles = max(session.total_vehicles, payload.total_vehicles)
    session.average_fps = payload.average_fps
    if payload.source_fps is not None:
        session.source_fps = payload.source_fps
    if payload.source_duration_seconds is not None:
        session.source_duration_seconds = payload.source_duration_seconds
    session.ended_at = datetime.now(timezone.utc)
    session.status = SessionStatus.error if payload.status == "error" else (SessionStatus.completed if payload.status == "completed" else SessionStatus.stopped)
    camera = db.get(Camera, session.camera_id)
    if camera:
        camera.status = CameraStatus.error if payload.status == "error" else CameraStatus.inactive
    db.commit()
    return {"status": "ok"}


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
    return _benchmark_payload(row, 0)


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


@router.delete("/benchmarks/{benchmark_id}/marks/{mark_id}")
def delete_ground_truth_mark(benchmark_id: int, mark_id: int, db: Session = Depends(get_db)) -> dict:
    mark = db.get(GroundTruthCrossing, mark_id)
    if mark is None or mark.benchmark_id != benchmark_id:
        raise HTTPException(status_code=404, detail="Ground-truth mark not found")
    db.delete(mark)
    db.commit()
    return {"status": "deleted", "mark_id": mark_id}


@router.get("/benchmarks/{benchmark_id}/report")
def benchmark_report(benchmark_id: int, db: Session = Depends(get_db)) -> dict:
    benchmark = db.get(CountingBenchmark, benchmark_id)
    if benchmark is None:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    marks = list(db.scalars(
        select(GroundTruthCrossing)
        .where(GroundTruthCrossing.benchmark_id == benchmark_id)
        .order_by(GroundTruthCrossing.source_time_seconds, GroundTruthCrossing.id)
    ).all())
    all_events = list(db.scalars(
        select(VehicleEvent)
        .where(VehicleEvent.session_id == benchmark.session_id)
        .order_by(VehicleEvent.id)
    ).all())
    timed_events = [event for event in all_events if event.source_time_seconds is not None]
    report = match_crossings(marks, timed_events, benchmark.tolerance_seconds)
    trace_available = False
    if report["missed_items"]:
        try:
            response = httpx.post(
                f"{settings.ai_service_url}/benchmark-traces/{benchmark.session_id}/diagnose",
                json={
                    "times": [item["time"] for item in report["missed_items"]],
                    "window_seconds": min(1.0, max(0.35, benchmark.tolerance_seconds)),
                },
                timeout=8.0,
            )
            if response.is_success:
                trace = response.json()
                trace_available = bool(trace.get("available"))
                for item, diagnosis in zip(report["missed_items"], trace.get("items", [])):
                    item["diagnosis"] = diagnosis
        except Exception:
            trace_available = False
    miss_reason_counts: dict[str, int] = {}
    for item in report["missed_items"]:
        reason = (item.get("diagnosis") or {}).get("reason")
        if reason:
            miss_reason_counts[reason] = miss_reason_counts.get(reason, 0) + 1
    dominant_miss_reason = max(miss_reason_counts, key=miss_reason_counts.get) if miss_reason_counts else None
    report.update({
        "benchmark": _benchmark_payload(benchmark, len(marks)),
        "session_id": benchmark.session_id,
        "timed_ai_events": len(timed_events),
        "legacy_ai_events_without_source_time": len(all_events) - len(timed_events),
        "trace_available": trace_available,
        "miss_reason_counts": miss_reason_counts,
        "dominant_miss_reason": dominant_miss_reason,
        "ready": bool(marks) and len(timed_events) > 0,
    })
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
