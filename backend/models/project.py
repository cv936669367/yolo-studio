from typing import Optional
"""
Project Model - YOLO detection project
"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.orm.attributes import NO_VALUE
from core.database import Base


class Project(Base):
    __tablename__ = "projects"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Annotation type: "rectangle" or "polygon"
    anno_type: Mapped[str] = mapped_column(String(50), default="rectangle")
    
    # Data split ratios (train/val/test)
    train_ratio: Mapped[float] = mapped_column(Float, default=0.7)
    val_ratio: Mapped[float] = mapped_column(Float, default=0.15)
    test_ratio: Mapped[float] = mapped_column(Float, default=0.15)
    
    # Class labels as JSON array
    classes: Mapped[list] = mapped_column(JSON, default=list)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships (lazy="selectin" — async session 安全的预加载)
    images: Mapped[list["Image"]] = relationship("Image", back_populates="project", cascade="all, delete-orphan", lazy="selectin")
    train_runs: Mapped[list["TrainRun"]] = relationship("TrainRun", back_populates="project", cascade="all, delete-orphan", lazy="selectin")
    
    def to_dict(self):
        # 异步会话中禁止懒加载：仅在关系已加载时访问
        images_loaded = self._sa_instance_state.attrs["images"].loaded_value is not NO_VALUE
        runs_loaded = self._sa_instance_state.attrs["train_runs"].loaded_value is not NO_VALUE
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "anno_type": self.anno_type,
            "train_ratio": self.train_ratio,
            "val_ratio": self.val_ratio,
            "test_ratio": self.test_ratio,
            "classes": self.classes or [],
            "image_count": len(self.images) if images_loaded else 0,
            "train_run_count": len(self.train_runs) if runs_loaded else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
