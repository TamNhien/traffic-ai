from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.all_models import AIModel, Camera, CameraStatus, CountingSession, Direction, SessionStatus, VehicleCount, VehicleEvent, VehicleType
from app.schemas.camera import CameraCreate, CameraRead, CameraUpdate
from app.schemas.event import VehicleEventCreate, VehicleEventRead

router = APIRouter(prefix="/api")


class SessionFinish(BaseModel):
    status: str
    total_vehicles: int = 0
    average_fps: float | None = None
    last_error: str | None = None


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
    camera = Camera(**payload.model_dump())
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
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(camera, key, value)
    db.commit()
    db.refresh(camera)
    return camera


@router.get("/events", response_model=list[VehicleEventRead])
def list_events(limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)) -> list[VehicleEvent]:
    return list(db.scalars(select(VehicleEvent).order_by(VehicleEvent.detected_at.desc()).limit(limit)).all())


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
    } for row in rows]


@router.post("/cameras/{camera_id}/start")
def start_camera(camera_id: int, db: Session = Depends(get_db)) -> dict:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    running = db.scalar(select(CountingSession).where(CountingSession.camera_id == camera_id, CountingSession.status == SessionStatus.running).order_by(CountingSession.id.desc()))
    if running:
        # Reconcile stale DB state with the real AI registry. This makes replaying
        # the same MP4 reliable even when a previous finish callback was lost.
        ai_is_running = False
        try:
            probe = httpx.get(f"{settings.ai_service_url}/pipelines/{camera_id}", timeout=2.0)
            if probe.is_success:
                ai_state = probe.json()
                ai_is_running = ai_state.get("status") in {"starting", "running"}
        except Exception:
            ai_is_running = False
        if ai_is_running:
            raise HTTPException(status_code=409, detail="Camera already has a running session")
        running.status = SessionStatus.completed
        running.ended_at = datetime.now(timezone.utc)
        camera.status = CameraStatus.inactive
        db.commit()
    model = db.scalar(select(AIModel).where(AIModel.is_active.is_(True)).order_by(AIModel.id.desc()))
    session = CountingSession(camera_id=camera_id, model_id=model.id if model else None, status=SessionStatus.running)
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
    return {"session_id": session.id, "camera_id": camera_id, "pipeline": response.json()}


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


@router.post("/internal/events", response_model=VehicleEventRead, status_code=201)
def internal_event(payload: VehicleEventCreate, x_ai_token: str | None = Header(default=None), db: Session = Depends(get_db)) -> VehicleEvent:
    _assert_ai_token(x_ai_token)

    # Event delivery is retried by the AI service. Make this endpoint idempotent
    # for one ByteTrack ID inside one counting session so a network retry cannot
    # double-count a vehicle.
    existing = None
    if payload.session_id is not None and payload.tracking_id is not None:
        existing = db.scalar(select(VehicleEvent).where(
            VehicleEvent.session_id == payload.session_id,
            VehicleEvent.tracking_id == payload.tracking_id,
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
    session.ended_at = datetime.now(timezone.utc)
    session.status = SessionStatus.error if payload.status == "error" else (SessionStatus.completed if payload.status == "completed" else SessionStatus.stopped)
    camera = db.get(Camera, session.camera_id)
    if camera:
        camera.status = CameraStatus.error if payload.status == "error" else CameraStatus.inactive
    db.commit()
    return {"status": "ok"}


@router.get("/meta/vehicle-types")
def vehicle_types() -> list[str]:
    return [item.value for item in VehicleType]


@router.get("/meta/directions")
def directions() -> list[str]:
    return [item.value for item in Direction]
