from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.all_models import AIModel, Camera, CountingSession, Direction, VehicleEvent, VehicleType
from app.schemas.camera import CameraCreate, CameraRead
from app.schemas.event import VehicleEventCreate, VehicleEventRead

router = APIRouter(prefix="/api")


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    ai_status = "unavailable"
    try:
        response = httpx.get(f"{settings.ai_service_url}/health", timeout=2.0)
        if response.is_success:
            ai_status = response.json().get("status", "ok")
    except Exception:
        pass

    return {
        "status": "ok",
        "service": "backend",
        "database": "ok",
        "ai_service": ai_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)) -> dict:
    total_cameras = db.scalar(select(func.count(Camera.id))) or 0
    active_cameras = db.scalar(select(func.count(Camera.id)).where(Camera.status == "active")) or 0
    total_events = db.scalar(select(func.count(VehicleEvent.id))) or 0
    running_sessions = db.scalar(select(func.count(CountingSession.id)).where(CountingSession.status == "running")) or 0

    by_type_rows = db.execute(
        select(VehicleEvent.vehicle_type, func.count(VehicleEvent.id))
        .group_by(VehicleEvent.vehicle_type)
        .order_by(VehicleEvent.vehicle_type)
    ).all()
    by_direction_rows = db.execute(
        select(VehicleEvent.direction, func.count(VehicleEvent.id))
        .group_by(VehicleEvent.direction)
        .order_by(VehicleEvent.direction)
    ).all()

    return {
        "total_cameras": total_cameras,
        "active_cameras": active_cameras,
        "total_events": total_events,
        "running_sessions": running_sessions,
        "by_vehicle_type": {str(row[0].value if hasattr(row[0], "value") else row[0]): row[1] for row in by_type_rows},
        "by_direction": {str(row[0].value if hasattr(row[0], "value") else row[0]): row[1] for row in by_direction_rows},
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


@router.get("/events", response_model=list[VehicleEventRead])
def list_events(
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[VehicleEvent]:
    stmt = select(VehicleEvent).order_by(VehicleEvent.detected_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())


@router.post("/events", response_model=VehicleEventRead, status_code=status.HTTP_201_CREATED)
def create_event(payload: VehicleEventCreate, db: Session = Depends(get_db)) -> VehicleEvent:
    if db.get(Camera, payload.camera_id) is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    values = payload.model_dump(exclude_none=True)
    event = VehicleEvent(**values)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/models")
def list_models(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(AIModel).order_by(AIModel.id.desc())).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "version": row.version,
            "architecture": row.architecture,
            "model_path": row.model_path,
            "precision": row.precision,
            "recall": row.recall,
            "map50": row.map50,
            "map50_95": row.map50_95,
            "is_active": row.is_active,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/meta/vehicle-types")
def vehicle_types() -> list[str]:
    return [item.value for item in VehicleType]


@router.get("/meta/directions")
def directions() -> list[str]:
    return [item.value for item in Direction]
