from typing import Optional
"""
Annotation Model - Bounding box or polygon annotations
"""
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Float, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base


class Annotation(Base):
    __tablename__ = "annotations"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    image_id: Mapped[int] = mapped_column(ForeignKey("images.id", ondelete="CASCADE"), index=True)
    
    # Annotation type: "rectangle" or "polygon"
    anno_type: Mapped[str] = mapped_column(String(50), default="rectangle")
    
    # Class label
    class_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    
    # For rectangle: {"x": float, "y": float, "w": float, "h": float} (normalized 0-1)
    bbox: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # For polygon: [{"x": float, "y": float}, ...] (normalized 0-1)
    points: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    image: Mapped["Image"] = relationship("Image", back_populates="annotations", lazy="joined")
    
    def to_dict(self):
        data = {
            "id": self.id,
            "image_id": self.image_id,
            "anno_type": self.anno_type,
            "class_name": self.class_name,
            "bbox": self.bbox,
            "points": self.points,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        return data
