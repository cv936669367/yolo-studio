from typing import Optional
"""
TrainRun Model - Training run records
"""
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Float, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base


class TrainRun(Base):
    __tablename__ = "train_runs"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    
    # Model configuration
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "yolov8s"
    
    # Training parameters
    epochs: Mapped[int] = mapped_column(Integer, default=100)
    img_size: Mapped[int] = mapped_column(Integer, default=640)
    batch_size: Mapped[int] = mapped_column(Integer, default=16)
    
    # Status: "pending", "running", "completed", "failed"
    status: Mapped[str] = mapped_column(String(20), default="pending")
    
    # Results (filled after training completes)
    final_map50: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    final_map50_95: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precision: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recall: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Metrics per epoch as JSON array
    metrics_history: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    
    # Output paths
    weights_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    results_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    
    # Log output
    log_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="train_runs", lazy="joined")
    
    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "model_name": self.model_name,
            "epochs": self.epochs,
            "img_size": self.img_size,
            "batch_size": self.batch_size,
            "status": self.status,
            "final_map50": self.final_map50,
            "final_map50_95": self.final_map50_95,
            "precision": self.precision,
            "recall": self.recall,
            "metrics_history": self.metrics_history or [],
            "weights_path": self.weights_path,
            "results_path": self.results_path,
            "log_output": self.log_output,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
