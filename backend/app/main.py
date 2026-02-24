"""
ATVISION Main Application
FastAPI + Svelte Monolithic App
"""
import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.db import init_db, SessionLocal
from app.models.user import User, UserRole
from app.models.project import Project, ProjectStatus
from app.utils.security import get_password_hash
from app.api import auth, datasets, projects, models, training, reports, system, users
from app.workers.campaign_cleanup_worker import campaign_cleanup_worker
from app.workers.trash_cleanup_worker import trash_cleanup_worker
from app.services.scheduler_service import scheduler_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup
    print("🚀 Starting ATVISION...")
    
    # Initialize database
    init_db()
    print("✅ Database initialized")
    
    # Create default admin user if not exists
    db = SessionLocal()
    try:
        # Ensure admin user exists
        admin = db.query(User).filter(User.email == "admin@atvision.com").first()
        if not admin:
            admin = User(
                email="admin@atvision.com",
                hashed_password=get_password_hash("admin"),
                role=UserRole.ADMIN
            )
            db.add(admin)
            db.commit()
            print("✅ Default admin user created (email: admin@atvision.com, password: admin)")
        
        # Keep regular admin for backward compatibility
        admin = db.query(User).filter(User.email == "admin@atvision.com").first()
        if not admin:
            admin = User(
                email="admin@atvision.com",
                hashed_password=get_password_hash("admin"),
                role=UserRole.ADMIN
            )
            db.add(admin)
            db.commit()
            print("✅ Default admin user created (email: admin@atvision.com, password: admin)")
        
        # Create "Based" system project if not exists
        based_project = db.query(Project).filter(Project.name == "Based").first()
        if not based_project:
            # Use admin as creator
            creator = admin
            based_project = Project(
                name="Based",
                dataset_id=None,
                task_type="classify, detect, segment",
                status=ProjectStatus.CREATED.value,
                is_system=True,
                creator_id=creator.id
            )
            db.add(based_project)
            db.commit()
            print("✅ System project 'Based' created for hosting predefined models")
    finally:
        db.close()
    
    # Ensure data directories exist
    os.makedirs(settings.datasets_dir, exist_ok=True)
    os.makedirs(settings.models_dir, exist_ok=True)
    os.makedirs(settings.predictions_dir, exist_ok=True)
    os.makedirs(settings.uploads_dir, exist_ok=True)
    print("✅ Data directories created")
    
    # Start campaign cleanup worker
    campaign_cleanup_worker.start()
    
    # Start trash cleanup worker
    trash_cleanup_worker.start()
    
    # Start scheduler service
    scheduler_service.start()
    scheduler_service.restore_schedules()
    
    print(f"🎯 ATVISION {settings.APP_VERSION} is ready!")
    
    yield
    
    # Shutdown
    print("👋 Shutting down ATVISION...")
    campaign_cleanup_worker.stop()
    trash_cleanup_worker.stop()
    scheduler_service.stop()


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="ATVision Hub - Monolithic FastAPI + Svelte Application",
    lifespan=lifespan
)

# Configure CORS (for development)
if settings.DEBUG or settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include API routers
app.include_router(auth.router)
app.include_router(users.router)

# Import and mount profile router
from app.api import profile
app.include_router(profile.router)

app.include_router(datasets.router)
app.include_router(projects.router)
app.include_router(models.router)
app.include_router(training.router)
app.include_router(reports.router)
app.include_router(system.router)

# Import and mount API keys router
from app.api import api_keys
app.include_router(api_keys.router)

# Import and mount uploads router
from app.api import uploads
app.include_router(uploads.router)

# Import and mount recognition catalogs router
from app.api import recognition_catalogs
app.include_router(recognition_catalogs.router)

# Import and mount unified inference router - Model-agnostic
from app.api import inference
app.include_router(inference.router)

# Import and mount external inference router - Public API with API key auth
from app.api import external_inference
app.include_router(external_inference.router)

# Mount data directory for serving uploaded files (profile images, etc.)
DATA_DIR = Path(__file__).parent.parent / "data"
if DATA_DIR.exists():
    app.mount("/api/data", StaticFiles(directory=DATA_DIR), name="data")

# Mount static files for Svelte frontend (production)
FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    # Mount static assets
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")
    
    # Serve index.html for all non-API routes (SPA fallback)
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """
        Serve Svelte SPA for all non-API routes.
        """
        # Don't serve SPA for API routes
        if full_path.startswith("api/"):
            return {"detail": "Not Found"}
        
        # Serve index.html
        index_file = FRONTEND_DIST / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        
        return {"detail": "Frontend not built"}
else:
    @app.get("/")
    async def root():
        """
        Root endpoint when frontend is not built.
        """
        return {
            "message": "ATVISION API is running",
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "note": "Frontend not built. Run 'cd frontend && npm run build' to build the Svelte app."
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
