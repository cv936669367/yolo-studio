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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
