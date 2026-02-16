import json
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import AsyncSessionLocal
from .image_ingestion import process_directory_for_ingestion
from .image import scan_directory, compute_file_hash

if TYPE_CHECKING:
    from .vector_store import VectorStoreService


class IngestionJobService:
    """Service for managing directory processing jobs"""

    def __init__(self, vector_store: Optional["VectorStoreService"] = None):
        # Store progress for active jobs (in production, use Redis or similar)
        self._active_jobs: Dict[str, Dict[str, Any]] = {}
        self._vector_store = vector_store

    def set_vector_store(self, vector_store: "VectorStoreService") -> None:
        """Set the vector store service (needed for background tasks)"""
        self._vector_store = vector_store

    def create_job_id(self) -> str:
        """Generate a unique job ID"""
        return str(uuid.uuid4())

    def init_job(self, job_id: str) -> None:
        """Initialize a new job"""
        import time
        self._active_jobs[job_id] = {
            "status": "pending",
            "progress": 0.0,
            "total": 0,
            "processed": 0,
            "errors": [],
            "created_at": time.time(),
        }

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a job"""
        return self._active_jobs.get(job_id)

    def list_jobs(self) -> List[Dict[str, Any]]:
        """List all jobs"""
        return [{"job_id": k, **v} for k, v in self._active_jobs.items()]

    async def process_directory_job(
        self,
        directory_path: str,
        job_id: str,
        thumbnail_dir: Path,
    ):
        """Process a directory as a background job"""
        print(f"[DEBUG] [{job_id}] Starting job for path: {directory_path}")

        self._active_jobs[job_id] = {
            "status": "processing",
            "progress": 0.0,
            "total": 0,
            "processed": 0,
            "errors": [],
            "directory_path": str(directory_path),
        }

        if self._vector_store is None:
            raise RuntimeError("VectorStoreService not set. Call set_vector_store() first.")

        async def progress_callback(data: dict) -> None:
            self._active_jobs[job_id].update(data)

        try:
            # Use the ingestion logic from image_ingestion.py
            async with AsyncSessionLocal() as session:
                # Load current settings from DB
                from ..models.sql import Settings
                from sqlalchemy import select
                settings_res = await session.execute(select(Settings).limit(1))
                settings = settings_res.scalar_one_or_none()
                
                batch_size = 12
                image_extensions = None
                embedding_model = None
                
                if settings:
                    batch_size = settings.batch_size
                    image_extensions = settings.image_extensions
                    embedding_model = settings.embedding_model

                await process_directory_for_ingestion(
                    session=session,
                    directory_path=directory_path,
                    job_id=job_id,
                    thumbnail_dir=thumbnail_dir,
                    vector_store=self._vector_store,
                    progress_callback=progress_callback,
                    batch_size=batch_size,
                    image_extensions=image_extensions,
                    embedding_model=embedding_model,
                )

            self._active_jobs[job_id]["status"] = "completed"
            self._active_jobs[job_id]["progress"] = 1.0

        except Exception as e:
            import traceback

            error_msg = f"{type(e).__name__}: {str(e)}"
            print(f"[ERROR] [{job_id}] Job failed: {error_msg}")
            print(f"[ERROR] [{job_id}] Traceback: {traceback.format_exc()}")
            self._active_jobs[job_id] = {
                "status": "error",
                "progress": self._active_jobs.get(job_id, {}).get("progress", 0),
                "total": self._active_jobs.get(job_id, {}).get("total", 0),
                "processed": self._active_jobs.get(job_id, {}).get("processed", 0),
                "errors": [error_msg],
            }
