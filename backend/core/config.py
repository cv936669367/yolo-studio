"""
YOLO Studio - Core Configuration
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
MODEL_DIR = DATA_DIR / "models"
OUTPUT_DIR = DATA_DIR / "outputs"
TILE_DIR = DATA_DIR / "tiles"
DB_PATH = DATA_DIR / "yolo_studio.db"

# Ensure directories exist
for d in [DATA_DIR, UPLOAD_DIR, MODEL_DIR, OUTPUT_DIR, TILE_DIR]:
    d.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """Application settings"""
    APP_NAME: str = "YOLO Studio"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Database
    DATABASE_URL: str = f"sqlite+aiosqlite:///{DB_PATH}"
    
    # Storage
    UPLOAD_DIR: Path = UPLOAD_DIR
    MODEL_DIR: Path = MODEL_DIR
    OUTPUT_DIR: Path = OUTPUT_DIR
    
    # YOLO Defaults
    DEFAULT_EPOCHS: int = 100
    DEFAULT_IMG_SIZE: int = 640
    DEFAULT_BATCH_SIZE: int = 16
    DEFAULT_CONF_THRESHOLD: float = 0.25
    DEFAULT_IOU_THRESHOLD: float = 0.45
    
    class Config:
        env_file = ".env"


settings = Settings()
