from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.all_models import CameraStatus, SourceType


class CameraCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=2, max_length=50)
    source_type: SourceType
    source_url: str = Field(min_length=1)
    location: str | None = None
    description: str | None = None
    confidence_threshold: float = Field(default=0.35, ge=0.05, le=0.95)
    line_x1: float = Field(default=0.1, ge=0, le=1)
    line_y1: float = Field(default=0.5, ge=0, le=1)
    line_x2: float = Field(default=0.9, ge=0, le=1)
    line_y2: float = Field(default=0.5, ge=0, le=1)


class CameraRead(CameraCreate):
    id: int
    status: CameraStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
