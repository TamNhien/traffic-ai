from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CameraStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    error = "error"


class SourceType(str, Enum):
    rtsp = "rtsp"
    video = "video"
    webcam = "webcam"


class VehicleType(str, Enum):
    motorcycle = "motorcycle"
    bicycle = "bicycle"
    car = "car"
    bus = "bus"
    truck = "truck"
    other = "other"


class Direction(str, Enum):
    in_ = "in"
    out = "out"
    unknown = "unknown"


class SessionStatus(str, Enum):
    running = "running"
    completed = "completed"
    stopped = "stopped"
    error = "error"


def _enum(enum_cls: type[Enum], name: str) -> SAEnum:
    # PostgreSQL enums created by migration 0001 store the enum *values*.
    # Direction therefore stores "in", not the Python-safe member name "in_".
    return SAEnum(enum_cls, name=name, values_callable=lambda cls: [item.value for item in cls])


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(160))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    source_type: Mapped[SourceType] = mapped_column(_enum(SourceType, "source_type"), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[CameraStatus] = mapped_column(
        _enum(CameraStatus, "camera_status"), nullable=False, server_default="inactive"
    )
    confidence_threshold: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.12")
    line_x1: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.32")
    line_y1: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.59")
    line_x2: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.84")
    line_y2: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.59")
    road_x1: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.20")
    road_y1: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.16")
    road_x2: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.80")
    road_y2: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.16")
    road_x3: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.96")
    road_y3: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.98")
    road_x4: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.04")
    road_y4: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.98")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AIModel(Base):
    __tablename__ = "ai_models"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_ai_model_name_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    architecture: Mapped[str] = mapped_column(String(80), nullable=False)
    model_path: Mapped[str] = mapped_column(Text, nullable=False)
    training_dataset: Mapped[str | None] = mapped_column(String(255))
    precision: Mapped[float | None] = mapped_column(Float)
    recall: Mapped[float | None] = mapped_column(Float)
    map50: Mapped[float | None] = mapped_column(Float)
    map50_95: Mapped[float | None] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CountingSession(Base):
    __tablename__ = "counting_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True)
    model_id: Mapped[int | None] = mapped_column(ForeignKey("ai_models.id", ondelete="SET NULL"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[SessionStatus] = mapped_column(
        _enum(SessionStatus, "session_status"), nullable=False, server_default="running"
    )
    total_vehicles: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    average_fps: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class VehicleEvent(Base):
    __tablename__ = "vehicle_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("counting_sessions.id", ondelete="SET NULL"), index=True)
    model_id: Mapped[int | None] = mapped_column(ForeignKey("ai_models.id", ondelete="SET NULL"), index=True)
    tracking_id: Mapped[int | None] = mapped_column(Integer, index=True)
    vehicle_type: Mapped[VehicleType] = mapped_column(_enum(VehicleType, "vehicle_type"), nullable=False, index=True)
    direction: Mapped[Direction] = mapped_column(
        _enum(Direction, "vehicle_direction"), nullable=False, server_default="unknown", index=True
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    snapshot_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class VehicleCount(Base):
    __tablename__ = "vehicle_counts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True)
    vehicle_type: Mapped[VehicleType] = mapped_column(
        _enum(VehicleType, "vehicle_count_type"), nullable=False, index=True
    )
    direction: Mapped[Direction] = mapped_column(
        _enum(Direction, "vehicle_count_direction"), nullable=False, index=True
    )
    count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DatasetRecord(Base):
    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("slug", name="uq_datasets_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_camera_id: Mapped[int | None] = mapped_column(
        ForeignKey("cameras.id", ondelete="SET NULL"), index=True
    )
    source_url: Mapped[str | None] = mapped_column(Text)
    root_path: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="draft", index=True)
    sample_every_n_frames: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    image_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    labeled_images: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    box_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    train_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    val_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    test_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    reviewed_images: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    difficult_images: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    classes_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default='["motorcycle","bicycle","car","bus","truck"]',
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class TrainingRun(Base):
    __tablename__ = "training_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    base_model: Mapped[str] = mapped_column(String(160), nullable=False, server_default="yolo26s.pt")
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="queued", index=True)
    epochs: Mapped[int] = mapped_column(Integer, nullable=False, server_default="80")
    imgsz: Mapped[int] = mapped_column(Integer, nullable=False, server_default="640")
    batch_size: Mapped[int] = mapped_column(Integer, nullable=False, server_default="8")
    device: Mapped[str] = mapped_column(String(40), nullable=False, server_default="auto")
    current_epoch: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    progress: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")
    precision: Mapped[float | None] = mapped_column(Float)
    recall: Mapped[float | None] = mapped_column(Float)
    map50: Mapped[float | None] = mapped_column(Float)
    map50_95: Mapped[float | None] = mapped_column(Float)
    best_model_path: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
