"""
API Schemas - Pydantic models for request/response validation
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ─── Project Schemas ──────────────────────────────────────
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    anno_type: str = Field(default="rectangle", pattern="^(rectangle|polygon)$")
    classes: list[str] = Field(default_factory=lambda: ["person", "car", "truck", "bicycle", "dog", "cat"])
    train_ratio: float = Field(default=0.7, ge=0.5, le=0.9)
    val_ratio: float = Field(default=0.15, ge=0.05, le=0.25)
    test_ratio: float = Field(default=0.15, ge=0.05, le=0.25)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    anno_type: Optional[str] = Field(None, pattern="^(rectangle|polygon)$")
    classes: Optional[list[str]] = None
    train_ratio: Optional[float] = Field(None, ge=0.5, le=0.9)
    val_ratio: Optional[float] = Field(None, ge=0.05, le=0.25)
    test_ratio: Optional[float] = Field(None, ge=0.05, le=0.25)


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    anno_type: str
    train_ratio: float
    val_ratio: float
    test_ratio: float
    classes: list
    image_count: int
    train_run_count: int
    created_at: Optional[str]
    updated_at: Optional[str]
    
    model_config = {"from_attributes": True}


# ─── Image Schemas ────────────────────────────────────────
class ImageResponse(BaseModel):
    id: int
    project_id: int
    filename: str
    original_name: str
    width: Optional[int]
    height: Optional[int]
    file_size: Optional[int]
    split: str
    file_path: str
    created_at: Optional[str]
    annotation_count: int
    
    model_config = {"from_attributes": True}


class ImageSplitUpdate(BaseModel):
    image_ids: list[int]
    split: str = Field(..., pattern="^(train|val|test)$")


# ─── Annotation Schemas ──────────────────────────────────
class AnnotationCreate(BaseModel):
    image_id: int
    anno_type: str = Field(..., pattern="^(rectangle|polygon)$")
    class_name: str = Field(..., min_length=1, max_length=200)
    bbox: Optional[dict] = None  # {"x": float, "y": float, "w": float, "h": float}
    points: Optional[list] = None  # [{"x": float, "y": float}, ...]


class AnnotationResponse(BaseModel):
    id: int
    image_id: int
    anno_type: str
    class_name: str
    bbox: Optional[dict]
    points: Optional[list]
    created_at: Optional[str]
    
    model_config = {"from_attributes": True}


# ─── Train Schemas ────────────────────────────────────────
class TrainConfig(BaseModel):
    model_name: str = Field(default="yolov8s")
    epochs: int = Field(default=100, ge=1, le=1000)
    img_size: int = Field(default=632, ge=320, le=1280)
    batch_size: int = Field(default=16, ge=1, le=64)


class TrainRunResponse(BaseModel):
    id: int
    project_id: int
    model_name: str
    epochs: int
    img_size: int
    batch_size: int
    status: str
    final_map50: Optional[float]
    final_map50_95: Optional[float]
    precision: Optional[float]
    recall: Optional[float]
    metrics_history: list
    weights_path: Optional[str]
    results_path: Optional[str]
    log_output: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    created_at: Optional[str]
    
    model_config = {"from_attributes": True}


# ─── Inference Schema ─────────────────────────────────────
class InferenceRequest(BaseModel):
    run_id: int
    conf_threshold: float = Field(default=0.25, ge=0.01, le=1.0)
    iou_threshold: float = Field(default=0.45, ge=0.01, le=1.0)


class DetectionResult(BaseModel):
    class_name: str
    confidence: float
    bbox: dict  # {"x1": float, "y1": float, "x2": float, "y2": float}
    segment: Optional[list] = None  # 分割模型: 归一化轮廓点 [{"x","y"},...]


class InferenceResponse(BaseModel):
    success: bool
    detections: list[DetectionResult]
    image_width: int
    image_height: int
    inference_time_ms: float
    model_path: Optional[str] = None


# ─── Common Response ──────────────────────────────────────
class MessageResponse(BaseModel):
    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    detail: str
    error_code: str = "UNKNOWN_ERROR"
