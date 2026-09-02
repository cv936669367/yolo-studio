"""
YOLO Dataset Exporter
将数据库中的图片与标注导出为 YOLO 训练所需格式：

dataset/
├── data.yaml
├── images/
│   ├── train/xxx.jpg
│   ├── val/xxx.jpg
│   └── test/xxx.jpg
└── labels/
    ├── train/xxx.txt
    ├── val/xxx.txt
    └── test/xxx.txt
"""
import shutil
from pathlib import Path
from typing import List, Optional

from sqlalchemy import select

from core.config import settings
from models.project import Project
from models.image import Image
from models.annotation import Annotation


def _normalize_bbox(bbox: dict) -> Optional[dict]:
    """bbox 存储为归一化 {x, y, w, h}（左上角+宽高）→ YOLO {cx, cy, w, h}"""
    if not bbox:
        return None
    try:
        x = float(bbox.get("x", 0))
        y = float(bbox.get("y", 0))
        w = float(bbox.get("w", 0))
        h = float(bbox.get("h", 0))
    except (TypeError, ValueError):
        return None
    # 钳制到 [0,1] 且过滤无效框
    if w <= 0 or h <= 0:
        return None
    cx = min(max(x + w / 2, 0.0), 1.0)
    cy = min(max(y + h / 2, 0.0), 1.0)
    w = min(max(w, 0.0), 1.0)
    h = min(max(h, 0.0), 1.0)
    return {"cx": cx, "cy": cy, "w": w, "h": h}


def _points_to_bbox(points: List[dict]) -> Optional[dict]:
    """多边形点集 → 最小外接矩形（归一化坐标），用于统一按检测任务训练"""
    if not points or len(points) < 3:
        return None
    xs = [p.get("x", 0) for p in points if isinstance(p, dict)]
    ys = [p.get("y", 0) for p in points if isinstance(p, dict)]
    if not xs or not ys:
        return None
    x = min(xs)
    y = min(ys)
    w = max(xs) - x
    h = max(ys) - y
    if w <= 0 or h <= 0:
        return None
    return _normalize_bbox({"x": x, "y": y, "w": w, "h": h})


async def export_dataset(project_id: int, db_session) -> tuple[Path, int]:
    """导出项目标注为 YOLO 数据集目录，返回 (data.yaml 路径, 可训练图片数)"""
    # 读取项目与类别
    proj = (await db_session.execute(
        select(Project).where(Project.id == project_id)
    )).scalar_one_or_none()
    if not proj:
        raise ValueError(f"Project {project_id} not found")
    classes = list(proj.classes or [])
    if not classes:
        raise ValueError("Project has no classes")

    # 读取全部图片
    images = (await db_session.execute(
        select(Image).where(Image.project_id == project_id)
    )).scalars().all()

    # 读取全部标注（按 image_id 分组）
    annos = (await db_session.execute(
        select(Annotation).where(
            Annotation.image_id.in_([img.id for img in images])
        )
    )).scalars().all()

    by_image: dict[int, List[Annotation]] = {}
    for a in annos:
        by_image.setdefault(a.image_id, []).append(a)

    # 输出目录
    dataset_dir = settings.OUTPUT_DIR / str(project_id) / "dataset"
    img_dir = dataset_dir / "images"
    lbl_dir = dataset_dir / "labels"
    for split in ("train", "val", "test"):
        (img_dir / split).mkdir(parents=True, exist_ok=True)
        (lbl_dir / split).mkdir(parents=True, exist_ok=True)

    # 写入 data.yaml
    yaml_path = dataset_dir / "data.yaml"
    names_lines = "\n".join(f"  {i}: {name}" for i, name in enumerate(classes))
    yaml_path.write_text(
        f"path: {dataset_dir}\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"test: images/test\n"
        f"names:\n{names_lines}\n",
        encoding="utf-8",
    )

    # 按 split 分组（仅含标注的图片），保证 val 非空（ultralytics 要求）
    split_images: dict[str, list] = {"train": [], "val": [], "test": []}
    for img in images:
        if not by_image.get(img.id):
            continue  # 无标注图片不参与训练
        split = img.split if img.split in ("train", "val", "test") else "train"
        split_images[split].append(img)

    if not split_images["val"] and split_images["train"]:
        # 借一张训练图给验证集（同一文件可同时出现在 train/val）
        split_images["val"].append(split_images["train"][-1])

    train_count = sum(len(v) for v in split_images.values())

    # 按工程标注类型决定导出格式：
    #   rectangle → 检测格式（cls cx cy w h）
    #   polygon   → 分割格式（cls x1 y1 x2 y2 ... 多边形点）
    is_segment = (proj.anno_type == "polygon")

    def _write_img(img: Image, split: str):
        src = settings.UPLOAD_DIR / str(project_id) / img.filename
        dst = img_dir / split / img.filename
        # 图片文件缺失 → 直接报错，避免导出空数据集导致 ultralytics 报晦涩错误
        if not src.exists():
            raise FileNotFoundError(
                f"图片文件缺失: {img.original_name} (id={img.id})。"
                f"文件可能已被删除，请重新上传图片后再训练。"
            )
        if not dst.exists():
            shutil.copy2(src, dst)

        lines = []
        for a in by_image.get(img.id, []):
            if a.class_name not in classes:
                continue
            cls_id = classes.index(a.class_name)

            if is_segment:
                # 分割格式：优先多边形点，bbox 转 4 角点
                pts = a.points if (a.points and len(a.points) >= 3) else None
                if pts is None and a.bbox:
                    b = a.bbox
                    try:
                        x, y, w, h = float(b["x"]), float(b["y"]), float(b["w"]), float(b["h"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    pts = [
                        {"x": x, "y": y},
                        {"x": x + w, "y": y},
                        {"x": x + w, "y": y + h},
                        {"x": x, "y": y + h},
                    ]
                if pts is None:
                    continue
                line = f"{cls_id} " + " ".join(f"{p['x']:.6f} {p['y']:.6f}" for p in pts)
                lines.append(line)
            else:
                # 检测格式：bbox，多边形取外接矩形
                box = _normalize_bbox(a.bbox) if a.bbox else None
                if box is None and a.points:
                    box = _points_to_bbox(a.points)
                if box is None:
                    continue
                lines.append(f"{cls_id} {box['cx']:.6f} {box['cy']:.6f} {box['w']:.6f} {box['h']:.6f}")

        if lines:
            (lbl_dir / split / (Path(img.filename).stem + ".txt")).write_text(
                "\n".join(lines) + "\n", encoding="utf-8"
            )

    for split, imgs in split_images.items():
        for img in imgs:
            _write_img(img, split)

    return yaml_path, train_count
