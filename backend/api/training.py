"""
Training API - 真实 YOLO 训练管理
使用 ultralytics 执行真实训练，进度通过回调写入内存并定时落库。
"""
import asyncio
import json
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings, DB_PATH
from core.database import get_db
from core.dataset import export_dataset
from models.project import Project
from models.image import Image
from models.annotation import Annotation
from models.train_run import TrainRun
from api.schemas import TrainConfig, TrainRunResponse, MessageResponse

router = APIRouter(tags=["Training"])

# 运行中的训练任务: {run_id: {"running": bool, "progress": {...}}}
training_tasks = {}


def _db_update(run_id: int, **fields):
    """用同步 sqlite3 更新训练记录（训练线程内安全）"""
    sets = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [run_id]
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute(f"UPDATE train_runs SET {sets} WHERE id = ?", values)
        conn.commit()
    finally:
        conn.close()


def _db_read(run_id: int) -> dict:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM train_runs WHERE id = ?", (run_id,)
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


@router.get("/projects/{project_id}/runs", response_model=list)
async def list_train_runs(
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(TrainRun).where(TrainRun.project_id == project_id)
        .order_by(TrainRun.created_at.desc())
    )
    runs = result.scalars().all()
    items = []
    for r in runs:
        d = r.to_dict()
        # 制品信息：权重文件是否存在 + 大小
        best_pt = settings.OUTPUT_DIR / str(project_id) / f"run_{r.id}" / "weights" / "best.pt"
        d["has_weights"] = best_pt.exists()
        d["weights_size_mb"] = round(best_pt.stat().st_size / 1024 / 1024, 1) if best_pt.exists() else None
        # 已导出文件（onnx 等）
        exports = []
        if best_pt.parent.exists():
            for ext in ("onnx", "torchscript"):
                for f in best_pt.parent.glob(f"*.{ext}"):
                    exports.append({
                        "name": f.name,
                        "format": ext,
                        "size_mb": round(f.stat().st_size / 1024 / 1024, 1),
                    })
        d["exports"] = exports
        items.append(d)
    return items


@router.delete("/projects/{project_id}/runs/{run_id}")
async def delete_train_run(
    project_id: int,
    run_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除训练制品（数据库记录 + 全部产物文件）"""
    run = (await db.execute(select(TrainRun).where(TrainRun.id == run_id))).scalar_one_or_none()
    if not run or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="训练记录不存在")

    # 删除产物目录（权重、结果图、数据集、导出文件）
    run_dir = settings.OUTPUT_DIR / str(project_id) / f"run_{run_id}"
    if run_dir.exists():
        import shutil
        shutil.rmtree(run_dir, ignore_errors=True)

    await db.delete(run)
    await db.commit()
    return {"success": True, "message": f"制品 {run.model_name} (run {run_id}) 已删除"}


@router.get("/runs/{run_id}", response_model=dict)
async def get_train_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = (await db.execute(select(TrainRun).where(TrainRun.id == run_id))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Training run not found")
    data = run.to_dict()
    task = training_tasks.get(run_id)
    data["is_running"] = bool(task and task.get("running"))
    if task and task.get("progress"):
        data["progress"] = task["progress"]
    return data


@router.post("/projects/{project_id}/train", response_model=dict)
async def start_training(
    project_id: int,
    config: TrainConfig,
    db: AsyncSession = Depends(get_db),
):
    """启动真实 YOLO 训练"""
    proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    # 校验标注数据
    anno_result = await db.execute(
        select(Image.id).join(Annotation).where(Image.project_id == project_id).distinct()
    )
    annotated = anno_result.scalars().all()
    if len(annotated) < 2:
        raise HTTPException(
            status_code=400,
            detail=f"至少需要 2 张已标注图片，当前 {len(annotated)} 张",
        )
    if not proj.classes:
        raise HTTPException(status_code=400, detail="工程未配置类别")

    # 校验基线模型已下载（防止绕过前端直接调用）
    if not _model_file_exists(config.model_name):
        raise HTTPException(
            status_code=400,
            detail=f"基线模型 {config.model_name} 未下载，请先在模型列表下载",
        )

    run = TrainRun(
        project_id=project_id,
        model_name=config.model_name,
        epochs=config.epochs,
        img_size=config.img_size,
        batch_size=config.batch_size,
        status="pending",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    task_info = {"running": True, "progress": {
        "epoch": 0, "epochs": config.epochs, "map50": None, "loss": None,
        "history": [],
        "log": f"[{datetime.now().strftime('%H:%M:%S')}] 准备数据集...\n",
    }}
    training_tasks[run.id] = task_info

    thread = threading.Thread(
        target=_run_real_training,
        args=(run.id, project_id, config.model_dump()),
        daemon=True,
        name=f"train-run-{run.id}",
    )
    thread.start()

    return {**run.to_dict(), "message": f"训练已启动（{config.model_name}）"}


@router.post("/runs/{run_id}/cancel", response_model=MessageResponse)
async def cancel_training(run_id: int, db: AsyncSession = Depends(get_db)):
    run = (await db.execute(select(TrainRun).where(TrainRun.id == run_id))).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Training run not found")
    task = training_tasks.get(run_id)
    if not task or not task.get("running"):
        raise HTTPException(status_code=400, detail="训练未在运行")
    task["running"] = False
    return MessageResponse(message="正在停止训练...")


# ─── 真实训练执行 ────────────────────────────────────────────
def _run_real_training(run_id: int, project_id: int, config: dict):
    task = training_tasks[run_id]
    progress = task["progress"]

    def log_line(msg: str):
        progress["log"] = (progress.get("log", "") or "") + f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n"

    import asyncio

    async def prepare():
        from core.database import async_session
        async with async_session() as db:
            return await export_dataset(project_id, db)

    try:
        # 1. 导出数据集
        yaml_path, train_count = asyncio.run(prepare())
        log_line(f"数据集导出完成，可训练图片 {train_count} 张")
        _db_update(run_id, status="running", started_at=datetime.utcnow().isoformat())
        progress["phase"] = "training"

        # 2. 加载模型
        from ultralytics import YOLO
        import torch

        log_line(f"加载基线模型 {config['model_name']} ...")
        model = YOLO(config["model_name"])

        device = "mps" if torch.backends.mps.is_available() else "cpu"
        log_line(f"计算设备: {device}")

        run_dir = settings.OUTPUT_DIR / str(project_id) / f"run_{run_id}"

        # 3. 注册进度回调
        def on_epoch_end(trainer):
            if not task.get("running", False):
                trainer.stop_training = True
            m = trainer.metrics or {}
            epoch = getattr(trainer, "epoch", 0)
            progress["epoch"] = epoch
            progress["map50"] = m.get("metrics/mAP50(B)")
            progress["map50_95"] = m.get("metrics/mAP50-95(B)")
            progress["precision"] = m.get("metrics/precision(B)")
            progress["recall"] = m.get("metrics/recall(B)")
            loss = m.get("train/box_loss")
            progress["loss"] = loss
            # 累积完整历史（真实逐 epoch 指标）
            progress["history"].append({
                "epoch": epoch,
                "map50": progress["map50"],
                "map50_95": progress["map50_95"],
                "precision": progress["precision"],
                "recall": progress["recall"],
                "loss": loss,
            })
            progress["log"] = (progress.get("log", "") or "") + (
                f"[{datetime.now().strftime('%H:%M:%S')}] "
                f"Epoch {epoch}/{config['epochs']} | "
                f"mAP50 {progress['map50'] if progress['map50'] is not None else '-'} | "
                f"loss {loss if loss is not None else '-'}\n"
            )

        model.add_callback("on_train_epoch_end", on_epoch_end)

        log_line(f"开始训练: epochs={config['epochs']}, imgsz={config['img_size']}, batch={config['batch_size']}")

        # 4. 心跳线程：把内存进度写入数据库
        stop_heartbeat = threading.Event()

        def heartbeat():
            while not stop_heartbeat.is_set():
                p = dict(progress)
                _db_update(
                    run_id,
                    log_output=p.get("log", ""),
                    metrics_history=json.dumps(p.get("history", []), ensure_ascii=False),
                )
                stop_heartbeat.wait(2)

        hb = threading.Thread(target=heartbeat, daemon=True)
        hb.start()

        # 5. 执行训练
        results = model.train(
            data=str(yaml_path),
            epochs=config["epochs"],
            imgsz=config["img_size"],
            batch=config["batch_size"],
            device=device,
            workers=0,
            project=str(run_dir.parent),
            name=run_dir.name,
            exist_ok=True,
            verbose=False,
            plots=True,
        )

        # 6. 完成：读取权重与指标
        best_pt = run_dir / "weights" / "best.pt"
        results_csv = run_dir / "results.csv"
        final = dict(progress)
        _db_update(
            run_id,
            status="completed",
            completed_at=datetime.utcnow().isoformat(),
            final_map50=final.get("map50"),
            final_map50_95=final.get("map50_95"),
            precision=final.get("precision"),
            recall=final.get("recall"),
            metrics_history=json.dumps(progress.get("history", []), ensure_ascii=False),
            weights_path=f"/outputs/{project_id}/run_{run_id}/weights/best.pt",
            results_path=f"/outputs/{project_id}/run_{run_id}/results.csv",
            log_output=progress.get("log", ""),
        )
        stop_heartbeat.set()
        log_line("训练完成 ✓")
        task["running"] = False

    except Exception as e:
        try:
            _db_update(
                run_id,
                status="failed",
                completed_at=datetime.utcnow().isoformat(),
                log_output=(progress.get("log", "") or "")
                + f"\n[ERROR] {type(e).__name__}: {e}",
            )
        except Exception:
            pass
        task["running"] = False
    finally:
        task["running"] = False
        progress["phase"] = "done"


@router.get("/projects/{project_id}/runs/{run_id}/download")
async def download_model(
    project_id: int,
    run_id: int,
    db: AsyncSession = Depends(get_db),
):
    """下载训练好的 PyTorch 权重 (best.pt)"""
    run = (await db.execute(select(TrainRun).where(TrainRun.id == run_id))).scalar_one_or_none()
    if not run or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="训练记录不存在")

    best_pt = settings.OUTPUT_DIR / str(project_id) / f"run_{run_id}" / "weights" / "best.pt"
    if not best_pt.exists():
        raise HTTPException(status_code=404, detail="模型权重不存在，请先完成训练")

    from fastapi.responses import FileResponse
    return FileResponse(
        best_pt,
        filename=f"{run.model_name}-best.pt",
        media_type="application/octet-stream",
    )


# 支持的导出格式（依赖已安装的）
EXPORT_FORMATS = {
    "onnx": {"ext": "onnx", "label": "ONNX"},
    "torchscript": {"ext": "torchscript", "label": "TorchScript"},
}


@router.post("/projects/{project_id}/runs/{run_id}/export")
async def export_model(
    project_id: int,
    run_id: int,
    format: str = "onnx",
    db: AsyncSession = Depends(get_db),
):
    """导出训练模型为部署格式（线程池执行，不阻塞事件循环）"""
    fmt = format.lower()
    if fmt not in EXPORT_FORMATS:
        raise HTTPException(status_code=400, detail=f"不支持的格式: {format}，可选 {list(EXPORT_FORMATS)}")

    run = (await db.execute(select(TrainRun).where(TrainRun.id == run_id))).scalar_one_or_none()
    if not run or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="训练记录不存在")

    best_pt = settings.OUTPUT_DIR / str(project_id) / f"run_{run_id}" / "weights" / "best.pt"
    if not best_pt.exists():
        raise HTTPException(status_code=404, detail="模型权重不存在，请先完成训练")

    run_dir = settings.OUTPUT_DIR / str(project_id) / f"run_{run_id}"
    out_file = run_dir / f"{run.model_name}.{EXPORT_FORMATS[fmt]['ext']}"

    # 已导出过则直接返回
    if out_file.exists():
        return {
            "success": True,
            "format": fmt,
            "url": f"/outputs/{project_id}/run_{run_id}/{out_file.relative_to(run_dir)}",
            "size_mb": round(out_file.stat().st_size / 1024 / 1024, 1),
            "message": "模型已导出",
        }

    def _do_export():
        from ultralytics import YOLO
        model = YOLO(str(best_pt))
        model.export(format=fmt, imgsz=run.img_size or 640)

    try:
        await asyncio.to_thread(_do_export)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {e}")

    if not out_file.exists():
        # ultralytics 可能把导出文件放在 weights/ 子目录或以其他名称
        candidates = list(run_dir.glob(f"**/*.{EXPORT_FORMATS[fmt]['ext']}"))
        if candidates:
            out_file = candidates[0]
        else:
            raise HTTPException(status_code=500, detail="导出文件未生成")

    return {
        "success": True,
        "format": fmt,
        "url": f"/outputs/{project_id}/run_{run_id}/{out_file.relative_to(run_dir)}",
        "size_mb": round(out_file.stat().st_size / 1024 / 1024, 1),
        "message": f"模型已导出为 {EXPORT_FORMATS[fmt]['label']}",
    }


# ─── 模型下载 ────────────────────────────────────────────────
# 官方权重 release（与 ultralytics 8.4.x 对应）
_ASSETS_URL = "https://github.com/ultralytics/assets/releases/download/v8.4.0/{id}.pt"
# 国内 GitHub 加速镜像（实测 gh-proxy.com 可用；依次尝试，最后回退官方源）
_MIRRORS = [
    "https://gh-proxy.com/{url}",
    "https://ghfast.top/{url}",
    "https://ghproxy.net/{url}",
    "{url}",
]

AVAILABLE_MODELS = [
    # ── 目标检测 (rect 工程) ──
    {"id": "yolov8n", "name": "YOLOv8n", "family": "YOLOv8", "task": "detect", "size_mb": 6.2, "desc": "轻量快速"},
    {"id": "yolov8s", "name": "YOLOv8s", "family": "YOLOv8", "task": "detect", "size_mb": 22.5, "desc": "均衡首选"},
    {"id": "yolov8m", "name": "YOLOv8m", "family": "YOLOv8", "task": "detect", "size_mb": 49.7, "desc": "精度优先"},
    {"id": "yolov8l", "name": "YOLOv8l", "family": "YOLOv8", "task": "detect", "size_mb": 83.7, "desc": "高精度"},
    {"id": "yolov8x", "name": "YOLOv8x", "family": "YOLOv8", "task": "detect", "size_mb": 130.5, "desc": "最高精度"},
    {"id": "yolo11n", "name": "YOLO11n", "family": "YOLO11", "task": "detect", "size_mb": 5.9, "desc": "轻量快速"},
    {"id": "yolo11s", "name": "YOLO11s", "family": "YOLO11", "task": "detect", "size_mb": 22.5, "desc": "均衡首选"},
    {"id": "yolo11m", "name": "YOLO11m", "family": "YOLO11", "task": "detect", "size_mb": 49.9, "desc": "精度优先"},
    {"id": "yolo12n", "name": "YOLO12n", "family": "YOLO12", "task": "detect", "size_mb": 6.4, "desc": "新一代轻量"},
    {"id": "yolo12s", "name": "YOLO12s", "family": "YOLO12", "task": "detect", "size_mb": 23.0, "desc": "新一代均衡"},
    {"id": "yolo12m", "name": "YOLO12m", "family": "YOLO12", "task": "detect", "size_mb": 51.0, "desc": "新一代精度"},
    {"id": "yolo26n", "name": "YOLO26n", "family": "YOLO26", "task": "detect", "size_mb": 6.5, "desc": "最新轻量"},
    {"id": "yolo26s", "name": "YOLO26s", "family": "YOLO26", "task": "detect", "size_mb": 23.5, "desc": "最新均衡"},
    {"id": "yolo26m", "name": "YOLO26m", "family": "YOLO26", "task": "detect", "size_mb": 52.0, "desc": "最新精度"},
    # ── 实例分割 (polygon 工程) ──
    {"id": "yolov8n-seg", "name": "YOLOv8n-seg", "family": "YOLOv8-Seg", "task": "segment", "size_mb": 7.1, "desc": "轻量分割"},
    {"id": "yolov8s-seg", "name": "YOLOv8s-seg", "family": "YOLOv8-Seg", "task": "segment", "size_mb": 27.5, "desc": "均衡分割"},
    {"id": "yolov8m-seg", "name": "YOLOv8m-seg", "family": "YOLOv8-Seg", "task": "segment", "size_mb": 68.2, "desc": "精度分割"},
    {"id": "yolo11n-seg", "name": "YOLO11n-seg", "family": "YOLO11-Seg", "task": "segment", "size_mb": 6.5, "desc": "轻量分割"},
    {"id": "yolo11s-seg", "name": "YOLO11s-seg", "family": "YOLO11-Seg", "task": "segment", "size_mb": 27.5, "desc": "均衡分割"},
    {"id": "yolo12n-seg", "name": "YOLO12n-seg", "family": "YOLO12-Seg", "task": "segment", "size_mb": 7.2, "desc": "新一代轻量分割"},
    {"id": "yolo12s-seg", "name": "YOLO12s-seg", "family": "YOLO12-Seg", "task": "segment", "size_mb": 28.0, "desc": "新一代均衡分割"},
    {"id": "yolo26n-seg", "name": "YOLO26n-seg", "family": "YOLO26-Seg", "task": "segment", "size_mb": 7.3, "desc": "最新轻量分割"},
    {"id": "yolo26s-seg", "name": "YOLO26s-seg", "family": "YOLO26-Seg", "task": "segment", "size_mb": 28.5, "desc": "最新均衡分割"},
]

# 下载任务进度: {model_id: {"status", "progress", "size_mb", "error"}}
download_tasks = {}


def _model_file_exists(model_id: str) -> bool:
    """检查基线模型权重是否已下载（多位置：模型目录 / ultralytics 缓存 / 项目目录）"""
    fname = f"{model_id}.pt"
    candidates = [
        settings.MODEL_DIR / fname,
        Path(__file__).parent.parent / fname,          # backend/ 根目录
        Path.home() / "Library/Application Support/Ultralytics" / fname,
        Path.home() / ".cache" / "ultralytics" / fname,
    ]
    # ultralytics settings 里的 weights_dir
    try:
        import json as _json
        sfile = Path.home() / "Library/Application Support/Ultralytics/settings.json"
        if sfile.exists():
            wdir = _json.loads(sfile.read_text()).get("weights_dir")
            if wdir:
                p = Path(wdir)
                candidates.append(p / fname if p.is_absolute() else Path(__file__).parent.parent / p / fname)
    except Exception:
        pass
    return any(p.exists() and p.stat().st_size > 1024 * 1024 for p in candidates)


def _is_downloaded(model_id: str) -> bool:
    p = settings.MODEL_DIR / f"{model_id}.pt"
    return p.exists() and p.stat().st_size > 1024 * 1024


@router.get("/models/available", response_model=list)
async def list_available_models():
    """列出可用基线模型（含是否已下载）"""
    return [{**m, "downloaded": _is_downloaded(m["id"])} for m in AVAILABLE_MODELS]


@router.get("/models/download-status/{model_id}")
async def get_download_status(model_id: str):
    """查询模型下载进度"""
    task = download_tasks.get(model_id)
    if not task:
        return {"status": "idle", "progress": 0, "size_mb": 0}
    return task


@router.post("/models/download/{model_id}")
async def download_baseline_model(model_id: str):
    """后台线程 + 国内镜像下载预训练权重（带进度）"""
    valid_ids = [m["id"] for m in AVAILABLE_MODELS]
    if model_id not in valid_ids:
        raise HTTPException(status_code=400, detail=f"无效模型 ID: {valid_ids}")

    if _is_downloaded(model_id):
        return {"message": f"模型 {model_id} 已下载", "downloading": False}

    # 已在下载中则直接返回
    task = download_tasks.get(model_id)
    if task and task["status"] == "downloading":
        return {"message": f"模型 {model_id} 正在下载", "downloading": True}

    download_tasks[model_id] = {"status": "downloading", "progress": 0, "size_mb": 0, "error": None}
    thread = threading.Thread(
        target=_download_model_thread, args=(model_id,), daemon=True, name=f"dl-{model_id}"
    )
    thread.start()
    return {"message": f"开始下载 {model_id}", "downloading": True}


def _download_model_thread(model_id: str):
    """下载线程：依次尝试国内镜像，分块写入并更新进度"""
    target = settings.MODEL_DIR / f"{model_id}.pt"
    target.parent.mkdir(parents=True, exist_ok=True)
    task = download_tasks[model_id]
    urls = [m.format(url=_ASSETS_URL.format(id=model_id)) for m in _MIRRORS]

    import urllib.request

    for url in urls:
        tmp = target.with_suffix(".pt.part")
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
                        task["progress"] = round(done / total * 100, 1)
                        task["size_mb"] = round(done / 1024 / 1024, 1)
            if tmp.stat().st_size > 1024 * 1024:
                tmp.rename(target)
                task.update(status="done", progress=100,
                            size_mb=round(target.stat().st_size / 1024 / 1024, 1))
                return
        except Exception as e:
            if tmp.exists():
                tmp.unlink()
            task["error"] = f"{url.split('/')[2]}: {e}"
            continue

    task["status"] = "error"
    task["progress"] = 0
