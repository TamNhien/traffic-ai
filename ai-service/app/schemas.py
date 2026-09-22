from pydantic import BaseModel, Field


class SourceValidationRequest(BaseModel):
    source_type: str
    source_url: str


class PipelineStart(BaseModel):
    camera_id: int
    session_id: int
    model_id: int | None = None
    model_path: str | None = None
    source_type: str
    source_url: str
    confidence_threshold: float = Field(default=0.35, ge=0.05, le=0.95)
    line_x1: float = Field(default=0.1, ge=0, le=1)
    line_y1: float = Field(default=0.5, ge=0, le=1)
    line_x2: float = Field(default=0.9, ge=0, le=1)
    line_y2: float = Field(default=0.5, ge=0, le=1)
