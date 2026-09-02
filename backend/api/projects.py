"""
Project API - CRUD operations for YOLO detection projects
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import os

from core.database import get_db
from models.project import Project
from api.schemas import (
    ProjectCreate, ProjectUpdate, ProjectResponse, MessageResponse
)

router = APIRouter(prefix="/projects", tags=["Projects"])


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
    """Create a new project"""
    project = Project(
        name=data.name,
        description=data.description,
        anno_type=data.anno_type,
        classes=data.classes,
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
    """Update project"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    
    await db.flush()
    await db.refresh(project)
    return project.to_dict()


@router.delete("/{project_id}", response_model=MessageResponse)
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a project and all associated data（数据库记录 + 上传图片 + 训练产物）"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 删除数据库记录（级联：images → annotations，train_runs）
    await db.delete(project)
    await db.commit()

    # 删除上传图片目录
    from core.config import UPLOAD_DIR, OUTPUT_DIR
    import shutil
    project_dir = UPLOAD_DIR / str(project_id)
    if project_dir.exists():
        shutil.rmtree(project_dir, ignore_errors=True)

    # 删除训练产物（数据集、权重、结果图、导出文件等）
    output_dir = OUTPUT_DIR / str(project_id)
    if output_dir.exists():
        shutil.rmtree(output_dir, ignore_errors=True)

    return MessageResponse(message=f"Project '{project.name}' deleted successfully")
