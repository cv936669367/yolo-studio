"""
Tiles API - 超大图标注瓦片化

对大图（任一边 ≥ 阈值）按 1024px 网格切成 JPEG 瓦片并生成降采样预览，
前端标注画布按视口渲染瓦片、缩放小于 1 时用预览层，避免一次性解码全图。

目录结构（data/tiles/{project_id}/{image_id}/）：
  manifest.json      尺寸/行列/瓦片大小等元数据
  preview.jpg        最长边 2048 降采样预览
  tiles/x_y.jpg      瓦片（原图左上角为原点）
"""
import asyncio
import json
import threading
from math import ceil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings, TILE_DIR
from core.database import get_db
from models.image import Image

router = APIRouter(tags=["Tiles"])

TILE_THRESHOLD = 5500   # 长边 ≥ 该像素才瓦片化（手机/相机照片直显即可）
TILE_SIZE = 1024
PREVIEW_MAX = 2048

# 生成中防重：{project_id/image_id: True}
_generating = set()
_gen_lock = threading.Lock()


def _image_tile_dir(project_id: int, image_id: int) -> Path:
    return TILE_DIR / str(project_id) / str(image_id)


def remove_image_tiles(project_id: int, image_id: int):
    """删除某张图的瓦片缓存（图片删除时联动调用）"""
    import shutil
    d = _image_tile_dir(project_id, image_id)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _meta_urls(project_id: int, image_id: int) -> dict:
    return {
        "preview_url": f"/tiles/{project_id}/{image_id}/preview.jpg",
        "tile_prefix": f"/tiles/{project_id}/{image_id}/tiles/",
    }


def _generate_tiles(project_id: int, image_id: int, src_path: Path, w: int, h: int) -> dict:
    """同步生成瓦片与预览（在 to_thread 中执行），返回清单"""
    out = _image_tile_dir(project_id, image_id)
    tile_dir = out / "tiles"
    manifest = out / "manifest.json"

    if manifest.exists():
        try:
            meta = json.loads(manifest.read_text(encoding="utf-8"))
            if (meta.get("width") == w and meta.get("height") == h
                    and meta.get("tile_size") == TILE_SIZE):
                meta.update(_meta_urls(project_id, image_id))
                return meta
        except Exception:
            pass

    tile_dir.mkdir(parents=True, exist_ok=True)
    from PIL import Image as PILImage

    with PILImage.open(str(src_path)) as src:
        # 预览（保持宽高比，最长边 ≤ PREVIEW_MAX；thumbnail 就地缩放避免整图 RGB 拷贝）
        base = src if src.mode == "RGB" else src.convert("RGB")
        base.thumbnail((PREVIEW_MAX, PREVIEW_MAX), PILImage.LANCZOS)
        base.save(str(out / "preview.jpg"), quality=82)
        if base is not src:
            base.close()

        # 瓦片网格
        cols = ceil(w / TILE_SIZE)
        rows = ceil(h / TILE_SIZE)
        for ty in range(rows):
            for tx in range(cols):
                left, top = tx * TILE_SIZE, ty * TILE_SIZE
                right = min(left + TILE_SIZE, w)
                bottom = min(top + TILE_SIZE, h)
                region = src.crop((left, top, right, bottom)).convert("RGB")
                region.save(str(tile_dir / f"{tx}_{ty}.jpg"), quality=80)
                region.close()

    meta = {
        "tiled": True,
        "width": w,
        "height": h,
        "tile_size": TILE_SIZE,
        "cols": cols,
        "rows": rows,
        "preview_max": PREVIEW_MAX,
    }
    manifest.write_text(json.dumps(meta), encoding="utf-8")
    meta.update(_meta_urls(project_id, image_id))
    return meta


@router.get("/images/{image_id}/tile-info")
async def get_tile_info(image_id: int, db: AsyncSession = Depends(get_db)):
    """
    查询（并懒生成）大图瓦片清单。
    小图返回 {tiled: false}，前端继续走原图直显路径。
    """
    img = (await db.execute(select(Image).where(Image.id == image_id))).scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    src = settings.UPLOAD_DIR / str(img.project_id) / img.filename
    if not src.exists():
        raise HTTPException(status_code=404, detail="图片文件缺失")

    w, h = img.width, img.height
    if not w or not h:
        try:
            from PIL import Image as PILImage
            with PILImage.open(str(src)) as p:
                w, h = p.size
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"无法读取图片尺寸: {e}")

    if max(w, h) < TILE_THRESHOLD:
        return {"tiled": False, "width": w, "height": h, "threshold": TILE_THRESHOLD}

    # 懒生成（to_thread 避免阻塞事件循环）
    with _gen_lock:
        dup = (img.project_id, img.id) in _generating
    if not dup:
        with _gen_lock:
            _generating.add((img.project_id, img.id))
        try:
            meta = await asyncio.to_thread(_generate_tiles, img.project_id, img.id, src, w, h)
        finally:
            with _gen_lock:
                _generating.discard((img.project_id, img.id))
    else:
        meta = _generate_tiles(img.project_id, img.id, src, w, h)  # 已生成则直接读
    return meta
