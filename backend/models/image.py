from typing import Optional
"""
Image Model - Uploaded images for annotation
"""
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.orm.attributes import NO_VALUE
from core.database import Base


class Image(Base):
    __tablename__ = "images"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    
    # File info
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_name: Mapped[str] = mapped_column(String(500), nullable=False)
    
    # Image dimensions
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # File size in bytes
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 文件内容哈希 sha256（同工程上传去重）
    sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Data split: "train", "val", or "test"
    split: Mapped[str] = mapped_column(String(20), default="train")
    
    # Relative path for serving
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships (async session 安全的预加载)
    project: Mapped["Project"] = relationship("Project", back_populates="images", lazy="joined")
    annotations: Mapped[list["Annotation"]] = relationship(
        "Annotation", back_populates="image", cascade="all, delete-orphan", lazy="selectin"
    )
    
    def to_dict(self, include_annotations=False):
        # 异步会话中禁止懒加载：仅在关系已加载时访问
        ann_loaded = self._sa_instance_state.attrs["annotations"].loaded_value is not NO_VALUE
        data = {
            "id": self.id,
            "project_id": self.project_id,
            "filename": self.filename,
            "original_name": self.original_name,
            "width": self.width,
            "height": self.height,
            "file_size": self.file_size,
            "sha256": self.sha256,
            "split": self.split,
            "file_path": self.file_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "annotation_count": len(self.annotations) if ann_loaded else 0,
        }
        if include_annotations:
            data["annotations"] = [a.to_dict() for a in (self.annotations if ann_loaded else [])]
        return data
