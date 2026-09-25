from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.all_models import Direction, VehicleType


class VehicleEventCreate(BaseModel):
    camera_id: int
    session_id: int | None = None
    model_id: int | None = None
    tracking_id: int | None = None
    vehicle_type: VehicleType
    direction: Direction = Direction.unknown
    confidence: float = Field(ge=0.0, le=1.0)
    detected_at: datetime | None = None
    snapshot_path: str | None = None
    source_frame_index: int | None = Field(default=None, ge=0)
    source_time_seconds: float | None = Field(default=None, ge=0.0)
    crossing_method: str | None = None
    crossing_x: float | None = Field(default=None, ge=0.0, le=1.0)
    crossing_y: float | None = Field(default=None, ge=0.0, le=1.0)


class VehicleEventRead(BaseModel):
    id: int
    camera_id: int
    session_id: int | None
    model_id: int | None
    tracking_id: int | None
    vehicle_type: VehicleType
    direction: Direction
    confidence: float
    detected_at: datetime
    snapshot_path: str | None
    source_frame_index: int | None
    source_time_seconds: float | None
    crossing_method: str | None
    crossing_x: float | None
    crossing_y: float | None

    model_config = ConfigDict(from_attributes=True)
