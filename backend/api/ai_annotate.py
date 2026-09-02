"""
AI-Assisted Annotation API
1. ai-annotate: YOLO 预训练模型自动检测并生成标注框
2. smart-select: SAM 智能分割，画框后自动生成精确多边形标注（Roboflow Smart Polygon）
"""
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from models.project import Project
from models.image import Image
from models.annotation import Annotation

router = APIRouter(tags=["AI Annotation"])


class SmartSelectRequest(BaseModel):
    image_id: int
    prompt_type: str = "box"  # "box" | "point"
    bbox: Optional[dict] = None
    points: Optional[list] = None  # [{x, y, positive}]
    class_name: str
    preview: bool = False  # True=仅预览不写库（智能点选多点联动用）

# 模型加载缓存：避免每次请求重新加载
_model_cache = {}
_sam_cache = {}

# SAM 模型（智能选框/点选核心）：统一放 data/models/，国内镜像下载
SAM_MODEL_ID = "sam_b.pt"
SAM_SIZE_MB = 375  # 官方大小（用于展示）
SAM_PATH = settings.MODEL_DIR / SAM_MODEL_ID
SAM_URL = "https://github.com/ultralytics/assets/releases/download/v8.4.0/sam_b.pt"
SAM_MIRRORS = [
    "https://gh-proxy.com/{url}",
    "https://ghfast.top/{url}",
    "https://ghproxy.net/{url}",
    "{url}",
]
sam_download_task = {"status": "idle", "progress": 0, "size_mb": 0, "error": None}


def _sam_available() -> bool:
    return SAM_PATH.exists() and SAM_PATH.stat().st_size > 1024 * 1024


def _load_model(model_id: str):
    if model_id in _model_cache:
        return _model_cache[model_id]
    from ultralytics import YOLO
    model = YOLO(model_id)
    _model_cache[model_id] = model
    return model


def _load_sam():
    """加载完整版 SAM（sam_b.pt）。未下载时抛清晰错误"""
    if "sam" in _sam_cache:
        return _sam_cache["sam"]
    if not _sam_available():
        raise RuntimeError("SAM 模型未下载，请先在标注页下载（约 375MB）")
    from ultralytics import SAM
    model = SAM(str(SAM_PATH))
    _sam_cache["sam"] = model
    return model


# ─── SAM 下载管理 ────────────────────────────────────────
@router.get("/sam/status")
async def sam_status():
    """SAM 模型下载状态"""
    task = dict(sam_download_task)
    task["downloaded"] = _sam_available()
    task["size_mb"] = SAM_SIZE_MB
    return task


@router.post("/sam/download")
async def sam_download():
    """后台线程 + 国内镜像下载 SAM 模型"""
    if _sam_available():
        return {"message": "SAM 模型已下载", "downloading": False}
    if sam_download_task["status"] == "downloading":
        return {"message": "SAM 模型正在下载", "downloading": True}

    sam_download_task.update(status="downloading", progress=0, size_mb=0, error=None)
    threading = __import__("threading")
    t = threading.Thread(target=_download_sam_thread, daemon=True)
    t.start()
    return {"message": "开始下载 SAM 模型（约 375MB，国内镜像源）", "downloading": True}


@router.get("/sam/download-status")
async def sam_download_status():
    """SAM 下载进度"""
    return dict(sam_download_task)


def _download_sam_thread():
    """SAM 下载线程：依次尝试国内镜像，分块写入并更新进度"""
    import urllib.request
    settings.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SAM_PATH.with_suffix(".pt.part")

    for mirror in SAM_MIRRORS:
        url = mirror.format(url=SAM_URL)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp, open(tmp, "wb") as f:
                total = int(resp.headers.get("Content-Length", 0))
                done = 0
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        sam_download_task["progress"] = round(done / total * 100, 1)
                        sam_download_task["size_mb"] = round(done / 1024 / 1024, 1)
            if tmp.exists() and tmp.stat().st_size > 1024 * 1024:
                tmp.rename(SAM_PATH)
                sam_download_task.update(
                    status="done", progress=100,
                    size_mb=round(SAM_PATH.stat().st_size / 1024 / 1024, 1),
                )
                return
        except Exception as e:
            if tmp.exists():
                tmp.unlink()
            sam_download_task["error"] = f"{url.split('/')[2]}: {e}"
            continue

    sam_download_task["status"] = "error"
    sam_download_task["progress"] = 0


def _match_class(det_name: str, project_classes: list) -> Optional[str]:
    """将检测到的 COCO 类别名匹配到工程类别（不区分大小写）"""
    det_lower = det_name.lower().strip()
    for cls in project_classes:
        if cls.lower().strip() == det_lower:
            return cls
    return None


def _simplify_polygon(points: list, min_dist: float = 0.006, max_points: int = 120) -> list:
    """多边形点抽稀：距离阈值 + 点数上限"""
    if len(points) <= 3:
        return points
    simplified = [points[0]]
    for p in points[1:]:
        last = simplified[-1]
        dx = p[0] - last[0]
        dy = p[1] - last[1]
        if (dx * dx + dy * dy) >= min_dist * min_dist:
            simplified.append(p)
    # 闭合点（首尾同点）不重复保存
    if simplified and len(simplified) > 2:
        first, last = simplified[0], simplified[-1]
        if abs(first[0] - last[0]) < 1e-9 and abs(first[1] - last[1]) < 1e-9:
            simplified = simplified[:-1]
    if len(simplified) > max_points:
        step = len(simplified) / max_points
        simplified = [simplified[int(i * step)] for i in range(max_points)]
    return simplified


@router.post("/projects/{project_id}/ai-annotate")
async def ai_annotate_image(
    project_id: int,
    image_id: int,
    model_id: str = "yolov8s",
    conf: float = 0.25,
    db: AsyncSession = Depends(get_db),
):
    """对单张图片执行 AI 辅助标注（真实检测）"""
    proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if not proj.classes:
        raise HTTPException(status_code=400, detail="工程未配置类别，无法匹配 AI 标注")

    img = (await db.execute(
        select(Image).where(Image.id == image_id, Image.project_id == project_id)
    )).scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    img_path = settings.UPLOAD_DIR / str(project_id) / img.filename
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="图片文件缺失")

    # 优先使用本工程已训练的最佳模型，否则用预训练基线
    best_pt = settings.OUTPUT_DIR / str(project_id)
    best_candidates = sorted(best_pt.glob("run_*/weights/best.pt"))
    if best_candidates:
        model = _load_model(str(best_candidates[-1]))
    else:
        model = _load_model(model_id)

    try:
        # 线程池执行推理，避免阻塞事件循环
        results = await asyncio.to_thread(
            model.predict,
            source=str(img_path),
            conf=conf,
            verbose=False,
            device="mps" if str(model.device).startswith("mps") else "cpu",
        )
    except Exception:
        results = await asyncio.to_thread(
            model.predict, source=str(img_path), conf=conf, verbose=False
        )

    detections = []
    names = model.names
    for r in results:
        img_w = r.orig_shape[1]
        img_h = r.orig_shape[0]
        for box in r.boxes:
            xyxy = box.xyxy[0].tolist()
            cls_id = int(box.cls[0])
            det_name = names.get(cls_id, f"class_{cls_id}")
            matched = _match_class(det_name, proj.classes)
            if not matched:
                continue  # 仅保留与工程类别匹配的结果
            x1, y1, x2, y2 = xyxy
            # 归一化: {x, y, w, h}（左上角+宽高），与前端标注格式一致
            norm_bbox = {
                "x": round(max(x1 / img_w, 0.0), 6),
                "y": round(max(y1 / img_h, 0.0), 6),
                "w": round(min((x2 - x1) / img_w, 1.0), 6),
                "h": round(min((y2 - y1) / img_h, 1.0), 6),
            }
            detections.append({
                "class_name": matched,
                "confidence": round(float(box.conf[0]), 4),
                "bbox": norm_bbox,
            })

    # 写入数据库
    created = []
    for det in detections:
        anno = Annotation(
            image_id=image_id,
            anno_type="rectangle",
            class_name=det["class_name"],
            bbox=det["bbox"],
            points=None,
        )
        db.add(anno)
        created.append(anno)
    await db.commit()
    for anno in created:
        await db.refresh(anno)

    return {
        "success": True,
        "model": "project-best" if best_candidates else model_id,
        "detections": detections,
        "created": [a.to_dict() for a in created],
        "message": f"AI 检测到 {len(detections)} 个目标并已生成标注",
    }


@router.post("/projects/{project_id}/smart-select")
async def smart_select_segment(
    project_id: int,
    data: SmartSelectRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Smart Select（Roboflow Smart Polygon）：
    - box 模式：画框提示，SAM 分割物体轮廓
    - point 模式：点击物体中心加区域（正点），点击背景减区域（负点），多点联动
    生成精确多边形标注。
    """
    proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if data.class_name not in (proj.classes or []):
        raise HTTPException(status_code=400, detail=f"类别 {data.class_name} 不在工程类别中")

    img = (await db.execute(
        select(Image).where(Image.id == data.image_id, Image.project_id == project_id)
    )).scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    img_path = settings.UPLOAD_DIR / str(project_id) / img.filename
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="图片文件缺失")

    img_w, img_h = img.width or 640, img.height or 640

    # SAM 未下载时给出明确提示（前端应提前检查）
    if not _sam_available():
        return {
            "success": False,
            "message": "SAM 模型未下载，请先在标注页下载（约 375MB，国内源）",
            "annotation": None,
        }

    model = _load_sam()

    if data.prompt_type == "point":
        # 点提示模式：正点加区域、负点减区域
        pts = data.points or []
        if not pts:
            raise HTTPException(status_code=400, detail="point 模式需要至少 1 个点")
        # SAM 期望 (1, N, 2) 的 points（1 张图 N 个点）和 (1, N) 的 labels
        # 若传 (N,2) 会被当作 N 张图各 1 点，导致只有第一个点生效
        sam_points = [[[int(p["x"] * img_w), int(p["y"] * img_h)] for p in pts]]
        sam_labels = [[1 if p.get("positive", True) else 0 for p in pts]]
        try:
            results = await asyncio.to_thread(
                model.predict, str(img_path),
                points=sam_points, labels=sam_labels, verbose=False,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"SAM 分割失败: {e}")
    else:
        # 框提示模式
        try:
            x = float(data.bbox["x"])
            y = float(data.bbox["y"])
            w = float(data.bbox["w"])
            h = float(data.bbox["h"])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(status_code=400, detail="bbox 格式无效")
        if w <= 0 or h <= 0:
            raise HTTPException(status_code=400, detail="框选区域无效")
        box_xyxy = [
            int(x * img_w), int(y * img_h),
            int((x + w) * img_w), int((y + h) * img_h),
        ]
        try:
            results = await asyncio.to_thread(
                model.predict, str(img_path), bboxes=[box_xyxy], verbose=False,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"SAM 分割失败: {e}")

    masks = results[0].masks
    if masks is None or len(masks) == 0:
        return {"success": False, "message": "未分割出目标，请调整提示点", "annotation": None}

    # 取面积最大的 mask（避免小碎片）
    best_idx = 0
    best_area = 0
    for i, xy in enumerate(masks.xy):
        if len(xy) >= 3:
            area = abs(sum(xy[j][0] * xy[(j + 1) % len(xy)][1] - xy[(j + 1) % len(xy)][0] * xy[j][1] for j in range(len(xy))) / 2)
            if area > best_area:
                best_area = area
                best_idx = i

    poly_px = masks.xy[best_idx]
    # 归一化 + 抽稀
    points_norm = [{"x": round(p[0] / img_w, 6), "y": round(p[1] / img_h, 6)} for p in poly_px]
    simplified = _simplify_polygon([(p["x"], p["y"]) for p in points_norm])
    points = [{"x": round(p[0], 6), "y": round(p[1], 6)} for p in simplified]

    if len(points) < 3:
        return {"success": False, "message": "分割结果过小", "annotation": None}

    # 预览模式：只返回点集，不写库（智能点选多点联动时由前端确认后创建）
    if data.preview:
        return {
            "success": True,
            "message": f"已生成 {len(points)} 点轮廓预览",
            "points": points,
            "points_count": len(points),
        }

    # 写入数据库（polygon 标注）
    anno = Annotation(
        image_id=data.image_id,
        anno_type="polygon",
        class_name=data.class_name,
        bbox=None,
        points=points,
    )
    db.add(anno)
    await db.commit()
    await db.refresh(anno)

    return {
        "success": True,
        "message": f"已生成 {len(points)} 点的精确轮廓标注",
        "annotation": anno.to_dict(),
        "points_count": len(points),
    }


@router.post("/projects/{project_id}/ai-clear")
async def ai_clear_annotations(
    project_id: int,
    image_id: int,
    db: AsyncSession = Depends(get_db),
):
    """清除单张图片的全部标注（用于撤销 AI 辅助标注）"""
    img = (await db.execute(
        select(Image).where(Image.id == image_id, Image.project_id == project_id)
    )).scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    await db.execute(delete(Annotation).where(Annotation.image_id == image_id))
    await db.commit()
    return {"success": True, "message": "已清除全部标注"}
