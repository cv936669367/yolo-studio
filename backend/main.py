"""
YOLO Studio - Main Application Entry Point
A Roboflow-like YOLO model building tool backend.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from core.config import settings, DB_PATH
from core.database import init_db
from api import projects, images, annotations, training, inference, ai_annotate


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup: initialize database
    await init_db()
    print(f"✅ Database initialized: {DB_PATH}")
    
    # Ensure upload directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.MODEL_DIR, exist_ok=True)
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    
    yield
    # Shutdown cleanup


app = FastAPI(
    title=settings.APP_NAME,
    description="YOLO Model Building Platform - Backend API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for uploads
if settings.UPLOAD_DIR.exists():
    app.mount("/uploads", StaticFiles(directory=str(settings.UPLOAD_DIR)), name="uploads")

# Mount static files for training outputs
if settings.OUTPUT_DIR.exists():
    app.mount("/outputs", StaticFiles(directory=str(settings.OUTPUT_DIR)), name="outputs")

# Register routers
app.include_router(projects.router, prefix="/api")
app.include_router(images.router, prefix="/api")
app.include_router(annotations.router, prefix="/api")
app.include_router(training.router, prefix="/api")
app.include_router(inference.router, prefix="/api")
app.include_router(ai_annotate.router, prefix="/api")


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/api/system/info")
async def system_info():
    """计算设备信息：CPU / GPU（含型号），供界面右上角展示"""
    import platform as _platform
    import subprocess

    info = {
        "device": "cpu",
        "device_label": "CPU",
        "device_name": _platform.processor() or _platform.machine(),
        "os": f"{_platform.system()} {_platform.machine()}",
        "python": _platform.python_version(),
        "torch": None,
        "ultralytics": None,
    }

    # torch 设备检测
    try:
        import torch
        info["torch"] = torch.__version__
        if torch.backends.mps.is_available():
            info["device"] = "mps"
            info["device_label"] = "GPU"
            # Apple Silicon 型号
            try:
                brand = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.brand_string"],
                    capture_output=True, text=True, timeout=3,
                ).stdout.strip()
                if brand:
                    info["device_name"] = brand
            except Exception:
                pass
        elif torch.cuda.is_available():
            info["device"] = "cuda"
            info["device_label"] = "GPU"
            try:
                info["device_name"] = torch.cuda.get_device_name(0)
            except Exception:
                pass
    except Exception:
        pass

    try:
        import ultralytics
        info["ultralytics"] = ultralytics.__version__
    except Exception:
        pass

    return info


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
