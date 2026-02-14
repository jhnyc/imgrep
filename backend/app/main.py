from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .core.database import init_db
from .api import directories, clusters, images, search, embeddings
from .core.config import CORS_ORIGINS, HOST, PORT, RELOAD, DATA_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    # Startup
    await init_db()
    from .services.sync_service import sync_sqlite_to_chroma
    await sync_sqlite_to_chroma()

    # Start background directory sync
    from .services.directory_sync import directory_sync_service
    await directory_sync_service.start_background_sync()

    yield

    # Shutdown
    await directory_sync_service.stop_background_sync()


app = FastAPI(
    title="Image Cluster API",
    description="Interactive image clustering with multi-modal search",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware - configured via environment variable
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# Mount static files for thumbnails
app.mount("/api/thumbnails", StaticFiles(directory=str(DATA_DIR)), name="thumbnails")

# Include routers
app.include_router(directories.router)
app.include_router(clusters.router)
app.include_router(images.router)
app.include_router(search.router)
app.include_router(embeddings.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Image Cluster API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=RELOAD,
    )
