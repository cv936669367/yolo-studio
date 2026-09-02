"""
Images API - Upload and manage images for projects
"""
import os
import uuid
import shutil
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from core.database import get_db
from core.config import settings
from models.project import Project
from models.image import Image
from api.schemas import ImageResponse, ImageSplitUpdate, MessageResponse

router = APIRouter(tags=["Images"])


def get_project_upload_dir(project_id: int) -> str:
    """Get or create upload directory for a project"""
    dir_path = settings.UPLOAD_DIR / str(project_id)
    dir_path.mkdir(parents=True, exist_ok=True)
    return str(dir_path)


@router.get("/projects/{project_id}/images", response_model=List[ImageResponse])
async def list_images(
    project_id: int,
    split: str = None,
    db: AsyncSession = Depends(get_db)
):
    """List all images in a project"""
    # Verify project exists
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")
    
    query = select(Image).where(Image.project_id == project_id)
    if split:
        query = query.where(Image.split == split)
    query = query.order_by(Image.created_at.desc())
    
    result = await db.execute(query)
    images = result.scalars().all()
    return [img.to_dict() for img in images]


@router.post("/projects/{project_id}/images/upload", response_model=List[ImageResponse])
async def upload_images(
    project_id: int,
    files: List[UploadFile] = File(...),
    split: str = Form(default="train"),
    db: AsyncSession = Depends(get_db)
):
    """Upload multiple images to a project"""
    # Verify project exists
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if split not in ("train", "val", "test"):
        raise HTTPException(status_code=400, detail="Invalid split value")
    
    upload_dir = get_project_upload_dir(project_id)
    uploaded_images = []
    
    from PIL import Image as PILImage
    
    for file in files:
        # Validate file type
        if not file.content_type or not file.content_type.startswith("image/"):
            continue
        
        # Generate unique filename
        ext = os.path.splitext(file.filename)[1].lower() or ".jpg"
        unique_name = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(upload_dir, unique_name)
        
        # Save file
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Get image dimensions
        try:
            with PILImage.open(file_path) as img:
                width, height = img.size
                file_size = os.path.getsize(file_path)
        except Exception:
            width, height, file_size = None, None, None
        
        # Create database record
        image = Image(
            project_id=project_id,
            filename=unique_name,
            original_name=file.filename,
            width=width,
            height=height,
            file_size=file_size,
            split=split,
            file_path=f"/uploads/{project_id}/{unique_name}",
        )
        db.add(image)
        uploaded_images.append(image)
    
    await db.flush()
    return [img.to_dict() for img in uploaded_images]


@router.delete("/images/{image_id}", response_model=MessageResponse)
async def delete_image(
    image_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete an image and its annotations"""
    result = await db.execute(select(Image).where(Image.id == image_id))
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Delete physical file
    full_path = os.path.join(settings.UPLOAD_DIR, str(image.project_id), image.filename)
    if os.path.exists(full_path):
        os.remove(full_path)
    
    await db.delete(image)
    return MessageResponse(message="Image deleted successfully")


@router.put("/images/split", response_model=MessageResponse)
async def update_image_splits(
    data: ImageSplitUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update split assignment for multiple images"""
    if data.split not in ("train", "val", "test"):
        raise HTTPException(status_code=400, detail="Invalid split value")
    
    result = await db.execute(select(Image).where(Image.id.in_(data.image_ids)))
    images = result.scalars().all()
    
    for img in images:
        img.split = data.split
    
    return MessageResponse(message=f"Updated {len(images)} images to {data.split}")


@router.post("/projects/{project_id}/auto-split", response_model=MessageResponse)
async def auto_split_dataset(
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Auto-split dataset based on project ratios"""
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    result = await db.execute(select(Image).where(Image.project_id == project_id))
    images = list(result.scalars().all())
    
    n = len(images)
    t_end = int(n * project.train_ratio)
    v_end = t_end + int(n * project.val_ratio)
    
    for i, img in enumerate(images):
        if i < t_end:
            img.split = "train"
        elif i < v_end:
            img.split = "val"
        else:
            img.split = "test"
    
    return MessageResponse(
        message=f"Auto-split completed: train={t_end}, val={v_end - t_end}, test={n - v_end}"
    )
