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
    confidence_threshold: float = Field(default=0.12, ge=0.05, le=0.95)
    line_x1: float = Field(default=0.1, ge=0, le=1)
    line_y1: float = Field(default=0.5, ge=0, le=1)
    line_x2: float = Field(default=0.9, ge=0, le=1)
    line_y2: float = Field(default=0.5, ge=0, le=1)


class DatasetExtractRequest(BaseModel):
    slug: str = Field(min_length=2, max_length=80)
    source_url: str = Field(min_length=1)
    every_n_frames: int = Field(default=10, ge=1, le=10000)
    max_images: int = Field(default=1200, ge=10, le=50000)


class DatasetAutoLabelRequest(BaseModel):
    slug: str = Field(min_length=2, max_length=80)
    model_path: str = Field(default="yolo26s.pt", min_length=1)
    confidence: float = Field(default=0.25, ge=0.05, le=0.95)


class DatasetPrepareRequest(BaseModel):
    slug: str = Field(min_length=2, max_length=80)
    train_ratio: float = Field(default=0.70, ge=0.50, lt=1.0)
    val_ratio: float = Field(default=0.20, gt=0.0, lt=0.50)
    seed: int = 2026


class TrainingStartRequest(BaseModel):
    run_id: int = Field(ge=1)
    dataset_slug: str = Field(min_length=2, max_length=80)
    base_model: str = Field(default="yolo26s.pt", min_length=1)
    epochs: int = Field(default=80, ge=1, le=1000)
    imgsz: int = Field(default=640, ge=320, le=1920)
    batch: int = Field(default=8, ge=1, le=256)
    device: str = "auto"

class AnnotationBox(BaseModel):
    class_id: int = Field(ge=0, le=4)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)


class AnnotationSaveRequest(BaseModel):
    boxes: list[AnnotationBox] = Field(default_factory=list)
    reviewed: bool = True
    difficult: bool = False
