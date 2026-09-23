from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CameraStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    error = "error"


class SourceType(str, enum.Enum):
    rtsp = "rtsp"
    video = "video"
    webcam = "webcam"


class VehicleType(str, enum.Enum):
    motorcycle = "motorcycle"
    bicycle = "bicycle"
    car = "car"
    bus = "bus"
    truck = "truck"
    other = "other"


class Direction(str, enum.Enum):
    in_ = "in"
    out = "out"
    unknown = "unknown"


class SessionStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    stopped = "stopped"
    error = "error"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(160))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType, name="source_type", values_callable=lambda x: [e.value for e in x]), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.18, nullable=False)
    line_x1: Mapped[float] = mapped_column(Float, default=0.1, nullable=False)
    line_y1: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    line_x2: Mapped[float] = mapped_column(Float, default=0.9, nullable=False)
    line_y2: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    status: Mapped[CameraStatus] = mapped_column(Enum(CameraStatus, name="camera_status", values_callable=lambda x: [e.value for e in x]), default=CameraStatus.inactive, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    sessions: Mapped[list[CountingSession]] = relationship(back_populates="camera")
    events: Mapped[list[VehicleEvent]] = relationship(back_populates="camera")


class AIModel(Base):
    __tablename__ = "ai_models"

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
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    sessions: Mapped[list[CountingSession]] = relationship(back_populates="model")
    events: Mapped[list[VehicleEvent]] = relationship(back_populates="model")

    __table_args__ = (UniqueConstraint("name", "version", name="uq_ai_model_name_version"),)


class CountingSession(Base):
    __tablename__ = "counting_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True)
    model_id: Mapped[int | None] = mapped_column(ForeignKey("ai_models.id", ondelete="SET NULL"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[SessionStatus] = mapped_column(Enum(SessionStatus, name="session_status", values_callable=lambda x: [e.value for e in x]), default=SessionStatus.running, nullable=False)
    total_vehicles: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    average_fps: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    camera: Mapped[Camera] = relationship(back_populates="sessions")
    model: Mapped[AIModel | None] = relationship(back_populates="sessions")
    events: Mapped[list[VehicleEvent]] = relationship(back_populates="session")


class VehicleEvent(Base):
    __tablename__ = "vehicle_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("counting_sessions.id", ondelete="SET NULL"), index=True)
    model_id: Mapped[int | None] = mapped_column(ForeignKey("ai_models.id", ondelete="SET NULL"), index=True)
    tracking_id: Mapped[int | None] = mapped_column(Integer, index=True)
    vehicle_type: Mapped[VehicleType] = mapped_column(Enum(VehicleType, name="vehicle_type", values_callable=lambda x: [e.value for e in x]), nullable=False, index=True)
    direction: Mapped[Direction] = mapped_column(Enum(Direction, name="vehicle_direction", values_callable=lambda x: [e.value for e in x]), default=Direction.unknown, nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    snapshot_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    camera: Mapped[Camera] = relationship(back_populates="events")
    session: Mapped[CountingSession | None] = relationship(back_populates="events")
    model: Mapped[AIModel | None] = relationship(back_populates="events")


class VehicleCount(Base):
    __tablename__ = "vehicle_counts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True)
    vehicle_type: Mapped[VehicleType] = mapped_column(Enum(VehicleType, name="vehicle_count_type", values_callable=lambda x: [e.value for e in x]), nullable=False, index=True)
    direction: Mapped[Direction] = mapped_column(Enum(Direction, name="vehicle_count_direction", values_callable=lambda x: [e.value for e in x]), nullable=False, index=True)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
