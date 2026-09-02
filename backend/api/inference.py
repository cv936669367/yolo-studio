"""
Inference API - 真实模型推理
优先加载训练完成的 best.pt，否则使用 ultralytics 预训练基线。
"""
import asyncio
import time
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from models.train_run import TrainRun
from api.schemas import InferenceResponse, DetectionResult

router = APIRouter(tags=["Inference"])

_model_cache = {}


def _load_model(path: str):
    if path in _model_cache:
        return _model_cache[path]
    from ultralytics import YOLO
    model = YOLO(path)
    _model_cache[path] = model
    return model


@router.post("/predict", response_model=InferenceResponse)
async def predict_image(
    file: UploadFile = File(...),
    run_id: int = Form(None),
    model_name: str = Form("yolov8s"),
    conf_threshold: float = Form(0.25),
    iou_threshold: float = Form(0.45),
    db: AsyncSession = Depends(get_db),
):
    """对上传图片执行真实目标检测"""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="文件必须是图片")

    content = await file.read()

    try:
        from PIL import Image as PILImage
        img = PILImage.open(BytesIO(content))
        img_width, img_height = img.size
    except Exception:
        raise HTTPException(status_code=400, detail="无法解析图片文件")

    # 确定模型路径：优先训练产物，其次基线
    model_path = model_name
    if run_id:
        result = await db.execute(select(TrainRun).where(TrainRun.id == run_id))
        run = result.scalar_one_or_none()
        if run and run.status == "completed":
            local_best = settings.OUTPUT_DIR / str(run.project_id) / f"run_{run_id}" / "weights" / "best.pt"
            if local_best.exists():
                model_path = str(local_best)

    start_time = time.time()
    model = _load_model(model_path)

    # ultralytics predict 不接受 BytesIO，需转为 numpy 数组
    import numpy as np
    from PIL import Image as PILImage
    img_array = np.array(PILImage.open(BytesIO(content)))

    try:
        results = await asyncio.to_thread(
            model.predict,
            source=img_array,
            conf=conf_threshold,
            iou=iou_threshold,
            verbose=False,
            device="mps" if str(model.device).startswith("mps") else "cpu",
        )
    except Exception:
        results = await asyncio.to_thread(
            model.predict, source=img_array, conf=conf_threshold, iou=iou_threshold, verbose=False
        )

    detections = []
    names = model.names
    for r in results:
        for box in r.boxes:
            xyxy = box.xyxy[0].tolist()
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            class_name = names.get(cls_id, f"class_{cls_id}")
            detections.append(DetectionResult(
                class_name=class_name,
                confidence=round(conf, 4),
                bbox={
                    "x1": round(xyxy[0], 2),
                    "y1": round(xyxy[1], 2),
                    "x2": round(xyxy[2], 2),
                    "y3": round(xyxy[3], 2),
                },
            ))

    inference_time = (time.time() - start_time) * 1000

    return InferenceResponse(
        success=True,
        detections=detections,
        image_width=img_width,
        image_height=img_height,
        inference_time_ms=round(inference_time, 2),
        model_path=model_path,
    )


@router.get("/runs/{run_id}/metrics")
async def get_training_metrics(run_id: int, db: AsyncSession = Depends(get_db)):
    """获取训练指标"""
    run = (await db.execute(select(TrainRun).where(TrainRun.id == run_id))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Training run not found")
    return {
        "run_id": run_id,
        "status": run.status,
        "final_metrics": {
            "map50": run.final_map50,
            "map50_95": run.final_map50_95,
            "precision": run.precision,
            "recall": run.recall,
        },
        "history": run.metrics_history or [],
        "log_output": run.log_output,
    }
