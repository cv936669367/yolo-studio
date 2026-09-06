"""
Project API - CRUD + 类别管理（重命名联动标注 / 改色 / 删除联动清理）
"""
import os
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete as sa_delete, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from core.database import get_db
from models.project import Project
from models.image import Image
from models.annotation import Annotation
from api.schemas import (
    ProjectCreate, ProjectUpdate, ProjectResponse, MessageResponse,
    ClassRenameRequest, ClassColorRequest,
)

router = APIRouter(prefix="/projects", tags=["Projects"])

# 默认调色板（与前端展示一致）
_DEFAULT_PALETTE = ["#1f5aff", "#0f9d58", "#e6a23c", "#e5484d",
                    "#7c3aed", "#0ea5e9", "#db2777", "#65a30d"]


def _seed_class_colors(classes: List[str], colors: dict) -> dict:
    """为没有颜色的类别自动分配默认色；保留已有颜色"""
    out = dict(colors or {})
    for i, cls in enumerate(classes):
        if cls not in out:
            out[cls] = _DEFAULT_PALETTE[i % len(_DEFAULT_PALETTE)]
    # 清理已被删除类别的残留色
    valid = set(classes)
    for k in [k for k in out if k not in valid]:
        out.pop(k, None)
    return out


def _normalize_color(color: str) -> str:
    c = color.strip().lower()
    if len(c) == 4:  # #abc → #aabbcc
        c = "#" + "".join(ch * 2 for ch in c[1:])
    return c


@router.get("", response_model=List[ProjectResponse])
async def list_projects(db: AsyncSession = Depends(get_db)):
    """Get all projects"""
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    projects = result.scalars().all()
    return [p.to_dict() for p in projects]


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new project（自动为类别分配默认颜色）"""
    colors = _seed_class_colors(data.classes or [], data.class_colors)
    project = Project(
        name=data.name,
        description=data.description,
        anno_type=data.anno_type,
        classes=data.classes,
        class_colors=colors,
        train_ratio=data.train_ratio,
        val_ratio=data.val_ratio,
        test_ratio=data.test_ratio,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return project.to_dict()


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get project by ID"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.to_dict()


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update project（classes 直接全量覆盖时保持颜色表同步）"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    # classes 变化后补齐/清理颜色表
    if project.classes is not None:
        project.class_colors = _seed_class_colors(project.classes, project.class_colors)

    await db.flush()
    await db.refresh(project)
    return project.to_dict()


# ─── 类别管理 ─────────────────────────────────────────────
@router.post("/{project_id}/classes/rename", response_model=dict)
async def rename_class(
    project_id: int,
    data: ClassRenameRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    重命名类别：
      - classes 数组中该位置保持（顺序即训练类别索引，不动）
      - 工程内全部旧名标注联动改名为新名
      - 颜色表键迁移
    注：历史训练 run 的模型内嵌名称不会改写（训练数据已固定），
       新标注与后续训练使用新名称。
    """
    proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    old = data.old_name.strip()
    new = data.new_name.strip()
    if old == new:
        raise HTTPException(status_code=400, detail="新旧名称相同")
    if not re.fullmatch(r"[\w-]{1,200}", new):
        raise HTTPException(status_code=400, detail="类别名仅支持中文/字母/数字/下划线/短横线")
    classes = list(proj.classes or [])
    if old not in classes:
        raise HTTPException(status_code=404, detail=f"类别 {old} 不存在")
    if new in classes:
        raise HTTPException(status_code=400, detail=f"类别 {new} 已存在")

    # 1) classes 原位替换
    proj.classes = [new if c == old else c for c in classes]
    # 2) 颜色键迁移
    colors = dict(proj.class_colors or {})
    if old in colors:
        colors[new] = colors.pop(old)
    proj.class_colors = colors

    # 3) 联动更新本工程内全部标注
    img_ids = select(Image.id).where(Image.project_id == project_id)
    await db.execute(
        sa_update(Annotation)
        .where(Annotation.image_id.in_(img_ids), Annotation.class_name == old)
        .values(class_name=new)
    )
    await db.flush()
    await db.refresh(proj)
    return {"success": True, "message": f"类别已重命名：{old} → {new}", "project": proj.to_dict()}


@router.put("/{project_id}/classes/color", response_model=dict)
async def set_class_color(
    project_id: int,
    data: ClassColorRequest,
    db: AsyncSession = Depends(get_db),
):
    """设置类别颜色（仅展示用，不参与训练数据）"""
    proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if data.name not in (proj.classes or []):
        raise HTTPException(status_code=404, detail=f"类别 {data.name} 不存在")

    colors = dict(proj.class_colors or {})
    colors[data.name] = _normalize_color(data.color)
    proj.class_colors = colors
    await db.flush()
    await db.refresh(proj)
    return {"success": True, "message": f"{data.name} 颜色已更新", "project": proj.to_dict()}


@router.delete("/{project_id}/classes/{class_name}", response_model=dict)
async def delete_class(
    project_id: int,
    class_name: str,
    db: AsyncSession = Depends(get_db),
):
    """删除类别：从类别表移除，并联动删除本工程该类别全部标注"""
    proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    name = class_name.strip()
    classes = list(proj.classes or [])
    if name not in classes:
        raise HTTPException(status_code=404, detail=f"类别 {name} 不存在")

    img_ids = select(Image.id).where(Image.project_id == project_id)
    annos = (await db.execute(
        select(Annotation.id).where(
            Annotation.image_id.in_(img_ids), Annotation.class_name == name)
    )).scalars().all()
    count = len(annos)
    if count:
        await db.execute(
            sa_delete(Annotation).where(
                Annotation.image_id.in_(img_ids), Annotation.class_name == name)
        )

    proj.classes = [c for c in classes if c != name]
    colors = dict(proj.class_colors or {})
    colors.pop(name, None)
    proj.class_colors = colors
    await db.flush()
    await db.refresh(proj)

    return {
        "success": True,
        "message": f"类别 {name} 已删除，联动清理标注 {count} 个",
        "deleted_annotations": count,
        "project": proj.to_dict(),
    }


@router.delete("/{project_id}", response_model=MessageResponse)
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a project and all associated data（数据库记录 + 上传图片 + 训练产物 + 瓦片缓存）"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 删除数据库记录（级联：images → annotations，train_runs）
    await db.delete(project)
    await db.commit()

    # 删除上传图片目录
    from core.config import UPLOAD_DIR, OUTPUT_DIR, TILE_DIR
    import shutil
    project_dir = UPLOAD_DIR / str(project_id)
    if project_dir.exists():
        shutil.rmtree(project_dir, ignore_errors=True)

    # 删除训练产物（数据集、权重、结果图、导出文件等）
    output_dir = OUTPUT_DIR / str(project_id)
    if output_dir.exists():
        shutil.rmtree(output_dir, ignore_errors=True)

    # 删除大图瓦片缓存
    tile_dir = TILE_DIR / str(project_id)
    if tile_dir.exists():
        shutil.rmtree(tile_dir, ignore_errors=True)

    return MessageResponse(message=f"Project '{project.name}' deleted successfully")
