"""
Auto-Label API - 自动标注（真实模型推理生成标注初稿）

将工程已训练的 best.pt（或任务匹配的已下载基线模型）对未标注图片
批量真实推理，把检测/分割结果写入 annotations 表作为人工微调的初稿。

工程类型约束：
  - rectangle 工程 → detect 模型（YOLOv8s 等）→ 生成矩形标注
  - polygon   工程 → segment 模型（YOLOv8s-seg 等）→ 生成多边形轮廓标注

后台线程逐图执行，进度经内存任务表暴露给前端轮询；可取消。
"""
import json
import sqlite3
import threading
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings, DB_PATH
from core.database import get_db
from models.project import Project
from models.train_run import TrainRun
from api.training import AVAILABLE_MODELS, _is_downloaded, model_task, project_need_seg
from api.ai_annotate import _load_model, _match_class, _simplify_polygon

router = APIRouter(tags=["Auto Label"])

# 运行中的自动标注任务: {project_id: task dict}
auto_label_tasks = {}


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _clamp01(v):
    return max(0.0, min(1.0, v))


# ─── 接口 ─────────────────────────────────────────────────
@router.post("/projects/{project_id}/auto-label")
async def start_auto_label(
    project_id: int,
    run_id: Optional[int] = None,
    model_name: Optional[str] = None,
    conf: float = Query(0.25, ge=0.05, le=0.95),
    iou: float = Query(0.45, ge=0.05, le=1.0),
    split: Optional[str] = Query(None, pattern="^(train|val|test)$"),
    only_unannotated: bool = Query(True),
    image_ids: Optional[str] = Query(None),  # 逗号分隔的图片 id（限定范围）
    db: AsyncSession = Depends(get_db),
):
    """
    对工程内未标注图片执行自动标注。
    模型来源二选一：
      run_id     → 本工程已完成训练 run 的 best.pt（类别体系与工程一致，推荐）
      model_name → 已下载且任务匹配的官方基线（COCO 80 类，按类别名匹配）
    """
    proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if not proj.classes:
        raise HTTPException(status_code=400, detail="工程未配置类别，无法匹配自动标注")

    need_seg = project_need_seg(proj.anno_type)
    task_type = "segment" if need_seg else "detect"

    # ── 解析模型来源 ──────────────────────────────────────
    if run_id and model_name:
        raise HTTPException(status_code=400, detail="run_id 与 model_name 只能指定其一")
    if run_id:
        run = (await db.execute(
            select(TrainRun).where(TrainRun.id == run_id, TrainRun.project_id == project_id)
        )).scalar_one_or_none()
        if not run:
            raise HTTPException(status_code=404, detail=f"run {run_id} 不存在于当前工程")
        if run.status != "completed":
            raise HTTPException(status_code=400, detail=f"run {run_id} 状态为 {run.status}，仅 completed 可用")
        best_pt = settings.OUTPUT_DIR / str(project_id) / f"run_{run.id}" / "weights" / "best.pt"
        if not best_pt.exists():
            raise HTTPException(status_code=404, detail=f"run {run.id} 权重文件缺失，请重新训练")
        if model_task(run.model_name) != task_type:
            raise HTTPException(
                status_code=400,
                detail=f"模型任务不匹配：当前工程为{'实例分割' if need_seg else '目标检测'}，"
                       f"run 模型 {run.model_name} 为 {model_task(run.model_name)}",
            )
        weights = str(best_pt)
        model_label = f"run {run.id} · {run.model_name}"
    elif model_name:
        m = next((x for x in AVAILABLE_MODELS if x["id"] == model_name), None)
        if not m:
            raise HTTPException(status_code=400, detail=f"未知基线模型: {model_name}")
        if not _is_downloaded(model_name):
            raise HTTPException(
                status_code=400,
                detail=f"基线模型 {model_name} 未下载，请先在训练页下载（约 {m['size_mb']}MB）",
            )
        if m["task"] != task_type:
            raise HTTPException(
                status_code=400,
                detail=f"模型任务不匹配：当前工程为{'实例分割' if need_seg else '目标检测'}，"
                       f"{model_name} 为 {m['task']}",
            )
        # 直接用本地文件绝对路径加载（避免 ultralytics 网络解析）
        weights = str(settings.MODEL_DIR / f"{model_name}.pt")
        model_label = f"{m['name']}（COCO 基线）"
    else:
        raise HTTPException(status_code=400, detail="请指定模型来源：run_id（工程已训模型）或 model_name（基线）")

    # 单工程同时只允许一个自动标注任务
    existing = auto_label_tasks.get(project_id)
    if existing and existing.get("running"):
        raise HTTPException(status_code=400, detail="该工程已有自动标注任务在运行，请等待完成或先取消")

    task = {
        "running": True,
        "status": "running",
        "cancel": False,
        "model_label": model_label,
        "conf": conf,
        "total": 0,
        "processed": 0,
        "created": 0,
        "skipped_annotated": 0,
        "failed_images": [],
        "started_at": _now(),
        "finished_at": None,
        "message": None,
        "error": None,
    }
    auto_label_tasks[project_id] = task

    params = {
        "weights": weights,
        "seg_mode": need_seg,
        "conf": conf,
        "iou": iou,
        "split": split,
        "only_unannotated": only_unannotated,
        "image_ids": [int(x) for x in image_ids.split(",")] if image_ids else None,
        "classes": list(proj.classes),
    }
    thread = threading.Thread(
        target=_auto_label_worker, args=(project_id, params),
        daemon=True, name=f"auto-label-{project_id}",
    )
    thread.start()

    return {
        "success": True,
        "message": f"自动标注已启动（模型: {model_label}，阈值 {conf}）",
        "model_label": model_label,
    }


@router.get("/projects/{project_id}/auto-label/status")
async def get_auto_label_status(project_id: int):
    """自动标注任务进度"""
    t = auto_label_tasks.get(project_id)
    if not t:
        return {"running": False, "status": "idle", "total": 0, "processed": 0,
                "created": 0, "message": "无任务记录"}
    return dict(t)


@router.post("/projects/{project_id}/auto-label/cancel")
async def cancel_auto_label(project_id: int):
    """取消自动标注（已生成的标注保留）"""
    t = auto_label_tasks.get(project_id)
    if not t or not t.get("running"):
        raise HTTPException(status_code=400, detail="没有运行中的自动标注任务")
    t["cancel"] = True
    return {"success": True, "message": "正在停止自动标注，已生成标注将保留"}


# ─── 后台工作线程 ─────────────────────────────────────────
def _auto_label_worker(project_id: int, p: dict):
    task = auto_label_tasks[project_id]
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        # 1. 收集目标图片（未标注 & 可选分组 / 指定图片）
        sql = "SELECT i.id, i.filename, i.width, i.height FROM images i WHERE i.project_id = ?"
        args: list = [project_id]
        if p["split"]:
            sql += " AND i.split = ?"
            args.append(p["split"])
        if p.get("image_ids"):
            sql += f" AND i.id IN ({','.join('?' * len(p['image_ids']))})"
            args.extend(int(x) for x in p["image_ids"])
        if p["only_unannotated"]:
            sql += " AND NOT EXISTS (SELECT 1 FROM annotations a WHERE a.image_id = i.id)"
        sql += " ORDER BY i.id ASC"

        rows = conn.execute(sql, args).fetchall()
        task["total"] = len(rows)
        if not rows:
            task.update(running=False, status="done", finished_at=_now(),
                        message="没有符合条件的图片（全部已标注或范围为空）")
            return

        # 2. 加载模型（共享缓存，避免重复加载）
        try:
            import torch
            device = "mps" if torch.backends.mps.is_available() else "cpu"
        except Exception:
            device = "cpu"

        model = _load_model(p["weights"])
        names = model.names

        insert_sql = (
            "INSERT INTO annotations (image_id, anno_type, class_name, bbox, points, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?)"
        )
        now_dt = datetime.utcnow()
        ts = str(now_dt)

        # 3. 逐图推理
        for row in rows:
            if task.get("cancel"):
                break
            img_id = int(row["id"])
            task["processed"] = task.get("processed", 0) + 1

            # 存在性 + 最新标注数复查（任务运行期间用户可能已手动标注）
            check = conn.execute(
                "SELECT (SELECT COUNT(*) FROM images WHERE id = ? AND project_id = ?) AS img_exists, "
                "(SELECT COUNT(*) FROM annotations WHERE image_id = ?) AS ann_cnt",
                (img_id, project_id, img_id),
            ).fetchone()
            if not check or not check["img_exists"]:
                task["failed_images"].append({"id": img_id, "reason": "图片已被删除"})
                continue
            if p["only_unannotated"] and check["ann_cnt"] > 0:
                task["skipped_annotated"] = task.get("skipped_annotated", 0) + 1
                continue

            img_path = settings.UPLOAD_DIR / str(project_id) / row["filename"]
            if not img_path.exists():
                task["failed_images"].append({"id": img_id, "reason": "图片文件缺失"})
                continue

            # 图片像素尺寸（归一化换算基准）
            W, H = row["width"], row["height"]
            if not W or not H:
                try:
                    from PIL import Image as PILImage
                    with PILImage.open(str(img_path)) as im:
                        W, H = im.size
                except Exception:
                    task["failed_images"].append({"id": img_id, "reason": "无法读取图片尺寸"})
                    continue
            W, H = int(W), int(H)

            try:
                results = model.predict(
                    source=str(img_path), conf=p["conf"], iou=p["iou"],
                    verbose=False, device=device,
                )
            except Exception:
                # 兜底 CPU（如 MPS 偶发不支持该图）
                results = model.predict(
                    source=str(img_path), conf=p["conf"], iou=p["iou"],
                    verbose=False, device="cpu",
                )

            annos_to_insert = []  # (image_id, anno_type, class_name, bbox_json, points_json)
            for r in results:
                if r.boxes is None or len(r.boxes) == 0:
                    continue
                # 分割轮廓：该 result 内与 boxes 按索引对齐。
                # 注意：单个实例的 m.xy 是 [ndarray(N,2)]（list 包一条或多条环），
                # 必须取 list 内的真实环（max len），不能对整个 list 判断长度。
                rings = []
                if p["seg_mode"] and r.masks is not None and len(r.masks):
                    for m in r.masks:
                        xy = m.xy
                        if xy is not None:
                            candidates = [ring for ring in xy if ring is not None and len(ring) >= 3]
                            rings.append(max(candidates, key=len) if candidates else None)
                        else:
                            rings.append(None)
                for bi, box in enumerate(r.boxes):
                    xyxy = box.xyxy[0].tolist()
                    x1, y1, x2, y2 = xyxy
                    # 极小框过滤：原始像素坐标下不足 4px 视为噪声
                    if (x2 - x1) < 4 or (y2 - y1) < 4:
                        continue
                    cls_id = int(box.cls[0])
                    det_name = names.get(cls_id, f"class_{cls_id}")
                    matched = _match_class(det_name, p["classes"])
                    if not matched:
                        continue  # 仅保留与工程类别匹配的结果

                    x1c, y1c = max(x1, 0.0), max(y1, 0.0)
                    x2c, y2c = min(x2, float(W)), min(y2, float(H))
                    if x2c - x1c <= 0 or y2c - y1c <= 0:
                        continue

                    if p["seg_mode"]:
                        # 多边形：优先分割轮廓 → 外接框四角兜底
                        poly_px = None
                        if bi < len(rings) and rings[bi] is not None:
                            poly_px = rings[bi]
                        points_norm = None
                        if poly_px is not None and len(poly_px) >= 3:
                            pts = [(_clamp01(px / W), _clamp01(py / H)) for px, py in poly_px]
                            simplified = _simplify_polygon(pts)
                            if len(simplified) >= 3:
                                points_norm = [{"x": round(q[0], 6), "y": round(q[1], 6)} for q in simplified]
                        if points_norm is None:
                            # 轮廓不可用 → 四角多边形兜底（与数据集导出格式一致）
                            points_norm = [
                                {"x": round(_clamp01(x1c / W), 6), "y": round(_clamp01(y1c / H), 6)},
                                {"x": round(_clamp01(x2c / W), 6), "y": round(_clamp01(y1c / H), 6)},
                                {"x": round(_clamp01(x2c / W), 6), "y": round(_clamp01(y2c / H), 6)},
                                {"x": round(_clamp01(x1c / W), 6), "y": round(_clamp01(y2c / H), 6)},
                            ]
                        annos_to_insert.append((
                            img_id, "polygon", matched,
                            None, json.dumps(points_norm, ensure_ascii=False),
                        ))
                    else:
                        bbox_norm = {
                            "x": round(_clamp01(x1c / W), 6),
                            "y": round(_clamp01(y1c / H), 6),
                            "w": round(_clamp01((x2c - x1c) / W), 6),
                            "h": round(_clamp01((y2c - y1c) / H), 6),
                        }
                        annos_to_insert.append((
                            img_id, "rectangle", matched,
                            json.dumps(bbox_norm, ensure_ascii=False), None,
                        ))

            # 4. 落库（逐图提交，任务中断也不丢已生成部分）
            if annos_to_insert:
                conn.executemany(insert_sql, [
                    (img_id, at, cn, bx, pxs, ts, ts) for img_id, at, cn, bx, pxs in annos_to_insert
                ])
                conn.commit()
                task["created"] = task.get("created", 0) + len(annos_to_insert)

        # 5. 收尾状态
        cancelled = bool(task.get("cancel"))
        done_msg = (
            f"自动标注{'已取消' if cancelled else '完成'}: 处理 {task['processed']}/{task['total']} 张，"
            f"共生成 {task.get('created', 0)} 个标注"
        )
        if task.get("skipped_annotated"):
            done_msg += f"，跳过已标注 {task['skipped_annotated']} 张"
        if task.get("failed_images"):
            done_msg += f"，失败 {len(task['failed_images'])} 张"
        task.update(running=False, finished_at=_now(),
                    status="cancelled" if cancelled else "done", message=done_msg)
    except Exception as e:
        task.update(running=False, status="error", finished_at=_now(),
                    error=f"{type(e).__name__}: {e}")
    finally:
        conn.close()
