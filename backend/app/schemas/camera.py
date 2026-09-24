from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.all_models import CameraStatus, SourceType


class _CameraSourceBase(BaseModel):
    @field_validator('source_url', mode='before', check_fields=False)
    @classmethod
    def normalize_source_url(cls, value):
        return value.strip() if isinstance(value, str) else value


class CameraCreate(_CameraSourceBase):
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=2, max_length=50)
    source_type: SourceType
    source_url: str = Field(min_length=1)
    location: str | None = None
    description: str | None = None
    confidence_threshold: float = Field(default=0.06, ge=0.02, le=0.95)
    line_x1: float = Field(default=0.32, ge=0, le=1)
    line_y1: float = Field(default=0.59, ge=0, le=1)
    line_x2: float = Field(default=0.84, ge=0, le=1)
    line_y2: float = Field(default=0.59, ge=0, le=1)
    road_x1: float = Field(default=0.20, ge=0, le=1)
    road_y1: float = Field(default=0.16, ge=0, le=1)
    road_x2: float = Field(default=0.80, ge=0, le=1)
    road_y2: float = Field(default=0.16, ge=0, le=1)
    road_x3: float = Field(default=0.96, ge=0, le=1)
    road_y3: float = Field(default=0.98, ge=0, le=1)
    road_x4: float = Field(default=0.04, ge=0, le=1)
    road_y4: float = Field(default=0.98, ge=0, le=1)


class CameraUpdate(_CameraSourceBase):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    code: str | None = Field(default=None, min_length=2, max_length=50)
    source_type: SourceType | None = None
    source_url: str | None = Field(default=None, min_length=1)
    location: str | None = None
    description: str | None = None
    confidence_threshold: float | None = Field(default=None, ge=0.02, le=0.95)
    line_x1: float | None = Field(default=None, ge=0, le=1)
    line_y1: float | None = Field(default=None, ge=0, le=1)
    line_x2: float | None = Field(default=None, ge=0, le=1)
    line_y2: float | None = Field(default=None, ge=0, le=1)
    road_x1: float | None = Field(default=None, ge=0, le=1)
    road_y1: float | None = Field(default=None, ge=0, le=1)
    road_x2: float | None = Field(default=None, ge=0, le=1)
    road_y2: float | None = Field(default=None, ge=0, le=1)
    road_x3: float | None = Field(default=None, ge=0, le=1)
    road_y3: float | None = Field(default=None, ge=0, le=1)
    road_x4: float | None = Field(default=None, ge=0, le=1)
    road_y4: float | None = Field(default=None, ge=0, le=1)


class CameraRead(CameraCreate):
    id: int
    status: CameraStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
