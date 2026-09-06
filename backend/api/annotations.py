"""
Annotations API - Manage bounding box and polygon annotations
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from core.database import get_db
from models.project import Project
from models.image import Image
from models.annotation import Annotation
from api.schemas import (
    AnnotationCreate, AnnotationResponse, MessageResponse
)

router = APIRouter(tags=["Annotations"])


@router.get("/images/{image_id}/annotations", response_model=List[AnnotationResponse])
async def list_annotations(
    image_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get all annotations for an image"""
    result = await db.execute(
        select(Annotation).where(Annotation.image_id == image_id)
    )
    annos = result.scalars().all()
    return [a.to_dict() for a in annos]


@router.post("/images/{image_id}/annotations", response_model=AnnotationResponse, status_code=201)
async def create_annotation(
    image_id: int,
    data: AnnotationCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new annotation for an image"""
    # Verify image exists
    img_result = await db.execute(select(Image).where(Image.id == image_id))
    if not img_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Validate annotation data based on type
    if data.anno_type == "rectangle" and not data.bbox:
        raise HTTPException(status_code=400, detail="Rectangle annotation requires bbox")
    if data.anno_type == "polygon" and (not data.points or len(data.points) < 3):
        raise HTTPException(status_code=400, detail="Polygon annotation requires at least 3 points")
    
    annotation = Annotation(
        image_id=image_id,
        anno_type=data.anno_type,
        class_name=data.class_name,
        bbox=data.bbox,
        points=data.points,
    )
    db.add(annotation)
    await db.flush()
    await db.refresh(annotation)
    return annotation.to_dict()


@router.put("/annotations/{annotation_id}", response_model=AnnotationResponse)
async def update_annotation(
    annotation_id: int,
    data: AnnotationCreate,
    db: AsyncSession = Depends(get_db)
):
    """Update an existing annotation"""
    result = await db.execute(select(Annotation).where(Annotation.id == annotation_id))
    anno = result.scalar_one_or_none()
    if not anno:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    anno.anno_type = data.anno_type
    anno.class_name = data.class_name
    anno.bbox = data.bbox
    anno.points = data.points
    
    await db.flush()
    await db.refresh(anno)
    return anno.to_dict()


@router.delete("/annotations/{annotation_id}", response_model=MessageResponse)
async def delete_annotation(
    annotation_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete an annotation"""
    result = await db.execute(select(Annotation).where(Annotation.id == annotation_id))
    anno = result.scalar_one_or_none()
    if not anno:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    await db.delete(anno)
    return MessageResponse(message="Annotation deleted")


@router.delete("/images/{image_id}/annotations/all", response_model=MessageResponse)
async def clear_annotations(
    image_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Clear all annotations for an image"""
    result = await db.execute(select(Annotation).where(Annotation.image_id == image_id))
    annos = result.scalars().all()
    
    count = 0
    for anno in annos:
        await db.delete(anno)
        count += 1
    
    return MessageResponse(message=f"Cleared {count} annotations")


@router.get("/projects/{project_id}/annotations/summary")
async def get_annotation_summary(
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get annotation summary for a project"""
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get all images with their annotation counts
    # 注意：一图多标注时 LEFT JOIN 会产生多行，统计图片数必须 DISTINCT，
    #       否则「图多标注的 split」的 images 数会虚高、总和与图片总数对不上
    from sqlalchemy import func
    result = await db.execute(
        select(Image.split, func.count(func.distinct(Image.id)), func.count(Annotation.id))
        .outerjoin(Annotation)
        .where(Image.project_id == project_id)
        .group_by(Image.split)
    )
    split_data = result.all()
    
    # Get per-class annotation counts
    class_result = await db.execute(
        select(Annotation.class_name, func.count(Annotation.id))
        .join(Image)
        .where(Image.project_id == project_id)
        .group_by(Annotation.class_name)
    )
    class_data = class_result.all()

    # Get per-class DISTINCT image counts（含该类别的图数，供界面与图总数对照）
    img_ids = select(Image.id).where(Image.project_id == project_id)
    class_img_result = await db.execute(
        select(Annotation.class_name, func.count(func.distinct(Annotation.image_id)))
        .where(Annotation.image_id.in_(img_ids))
        .group_by(Annotation.class_name)
    )
    class_img_data = class_img_result.all()

    total_images = sum(row[1] or 0 for row in split_data)
    total_annotations = sum(row[2] or 0 for row in split_data)
    
    return {
        "project_id": project_id,
        "total_images": total_images,
        "total_annotations": total_annotations,
        "classes": project.classes or [],
        "class_counts": {row[0]: row[1] for row in class_data},
        "class_image_counts": {row[0]: row[1] for row in class_img_data},
        "split_summary": {
            row[0]: {"images": row[1] or 0, "annotations": row[2] or 0}
            for row in split_data
        },
    }
