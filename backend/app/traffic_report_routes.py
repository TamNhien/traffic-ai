"""Read-only traffic reporting; global authentication/RBAC also protects exports."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.all_models import Camera, CountingSession, VehicleEvent
from app.traffic_reports import (MAX_AGGREGATE_ROWS, build_traffic_report, export_csv,
                                 export_pdf, export_xlsx, report_filters, utc_report_bounds)

router = APIRouter(prefix="/api/reports", tags=["Traffic reports"])


def _filters(start: date, end: date, group_by: str = "day",
             camera_id: int | None = Query(default=None, ge=1, le=2_147_483_647),
             vehicle_type: str | None = None,
             session_id: int | None = Query(default=None, ge=1, le=2_147_483_647)) -> dict:
    try:
        return report_filters(start, end, group_by, camera_id=camera_id,
                              vehicle_type=vehicle_type, session_id=session_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _load_report(db: Session, filters: dict) -> dict:
    start, end = utc_report_bounds(filters)
    if filters["camera_id"] is not None and db.get(Camera, filters["camera_id"]) is None:
        raise HTTPException(status_code=404, detail="Camera không tồn tại")
    if filters["session_id"] is not None:
        session = db.get(CountingSession, filters["session_id"])
        if session is None or (filters["camera_id"] is not None and session.camera_id != filters["camera_id"]):
            raise HTTPException(status_code=404, detail="Phiên không thuộc camera đã chọn")
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        hour = func.date_trunc("hour", func.timezone("Asia/Ho_Chi_Minh", VehicleEvent.detected_at))
    elif dialect == "sqlite":
        hour = func.strftime("%Y-%m-%dT%H:00:00", VehicleEvent.detected_at, "+7 hours")
    else:
        raise HTTPException(status_code=503, detail="Báo cáo hỗ trợ PostgreSQL và SQLite")
    dimensions = [hour, VehicleEvent.camera_id, Camera.name, VehicleEvent.vehicle_type,
                  VehicleEvent.direction, VehicleEvent.session_id]
    statement = select(hour.label("bucket"), VehicleEvent.camera_id, Camera.name.label("camera_name"),
                       VehicleEvent.vehicle_type, VehicleEvent.direction, VehicleEvent.session_id,
                       func.count(VehicleEvent.id).label("count")).join(Camera, Camera.id == VehicleEvent.camera_id).where(
                           VehicleEvent.detected_at >= start, VehicleEvent.detected_at < end)
    if filters["camera_id"] is not None:
        statement = statement.where(VehicleEvent.camera_id == filters["camera_id"])
    if filters["vehicle_type"] is not None:
        statement = statement.where(VehicleEvent.vehicle_type == filters["vehicle_type"])
    if filters["session_id"] is not None:
        statement = statement.where(VehicleEvent.session_id == filters["session_id"])
    rows = db.execute(statement.group_by(*dimensions).limit(MAX_AGGREGATE_ROWS + 1)).mappings().all()
    if len(rows) > MAX_AGGREGATE_ROWS:
        raise HTTPException(status_code=413, detail="Quá nhiều nhóm dữ liệu; thu hẹp ngày, camera hoặc phiên")
    return build_traffic_report(rows, filters)


@router.get("/traffic")
def traffic_report(filters: dict = Depends(_filters), db: Session = Depends(get_db)) -> dict:
    return _load_report(db, filters)


@router.get("/traffic/export")
def traffic_report_export(format: str = "xlsx", filters: dict = Depends(_filters), db: Session = Depends(get_db)) -> Response:
    exporters = {"csv": (export_csv, "text/csv; charset=utf-8"),
                 "xlsx": (export_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                 "pdf": (export_pdf, "application/pdf")}
    if format not in exporters:
        raise HTTPException(status_code=422, detail="format phải là xlsx, csv hoặc pdf")
    report = _load_report(db, filters)
    exporter, media = exporters[format]
    content = exporter(report)
    filename = f"traffic-report-{filters['start']}-{filters['end']}.{format}"
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"',
                                                       "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/sessions")
def report_sessions(camera_id: int | None = Query(default=None, ge=1, le=2_147_483_647),
                    limit: int = Query(default=100, ge=1, le=200), db: Session = Depends(get_db)) -> dict:
    statement = select(CountingSession)
    count = select(func.count(CountingSession.id))
    if camera_id is not None:
        statement = statement.where(CountingSession.camera_id == camera_id)
        count = count.where(CountingSession.camera_id == camera_id)
    total = int(db.scalar(count) or 0)
    sessions = db.scalars(statement.order_by(CountingSession.id.desc()).limit(limit)).all()
    return {"items": [{"id": item.id, "camera_id": item.camera_id,
                        "status": getattr(item.status, "value", item.status),
                        "started_at": item.started_at, "ended_at": item.ended_at, "total_vehicles": item.total_vehicles} for item in sessions],
            "limit": limit, "total": total, "truncated": total > limit}
