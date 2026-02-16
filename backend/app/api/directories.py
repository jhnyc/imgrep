from typing import List

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Depends
import shutil
from pathlib import Path

from ..dependencies import (
    get_ingestion_job_service,
    get_directory_sync_service,
    get_vector_store_service,
)
from ..core.config import THUMBNAILS_DIR, UPLOADS_DIR, ALLOWED_DIRECTORY_PREFIXES
from ..schemas.directory import (
    AddDirectoryRequest,
    JobStatusResponse,
    JobListResponse,
    TrackedDirectoryResponse,
    TrackedDirectoryListResponse,
    AddTrackedDirectoryRequest,
    SyncResultResponse,
    SyncTriggerResponse,
)

router = APIRouter(prefix="/api/directories", tags=["directories"])


@router.post("/add", response_model=dict)
async def add_directory(
    request: AddDirectoryRequest,
    background_tasks: BackgroundTasks,
    ingestion_job_service= Depends(get_ingestion_job_service),
):
    """Add a directory to process images from"""
    job_id = ingestion_job_service.create_job_id()

    # Check if directory exists
    dir_path = Path(request.path).expanduser().resolve()

    if not dir_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a valid directory: {dir_path}")

    # Security: Validate directory is within allowed prefixes
    if ALLOWED_DIRECTORY_PREFIXES:
        dir_str = str(dir_path)
        if not any(dir_str.startswith(prefix) for prefix in ALLOWED_DIRECTORY_PREFIXES):
            raise HTTPException(
                status_code=403,
                detail=f"Directory access denied. Allowed prefixes: {', '.join(ALLOWED_DIRECTORY_PREFIXES)}"
            )

    # Initialize job status
    ingestion_job_service.init_job(job_id)

    # Start background job
    background_tasks.add_task(ingestion_job_service.process_directory_job, str(dir_path), job_id, THUMBNAILS_DIR)

    return {"job_id": job_id, "status": "pending"}


@router.post("/upload", response_model=dict)
async def upload_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    ingestion_job_service= Depends(get_ingestion_job_service),
):
    """Upload files to process"""
    job_id = ingestion_job_service.create_job_id()

    # Create upload directory
    upload_dir = UPLOADS_DIR / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved_count = 0
    for file in files:
        if not file.filename:
            continue

        dest_path = upload_dir / Path(file.filename).name
        with dest_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        saved_count += 1

    # Initialize job status
    ingestion_job_service.init_job(job_id)

    # Start background job on the upload directory
    background_tasks.add_task(ingestion_job_service.process_directory_job, str(upload_dir), job_id, THUMBNAILS_DIR)

    return {"job_id": job_id, "status": "pending", "file_count": saved_count}


@router.get("/job/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    ingestion_job_service= Depends(get_ingestion_job_service),
):
    """Get status of a directory processing job"""
    status = ingestion_job_service.get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job_id,
        **status,
    )


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    ingestion_job_service= Depends(get_ingestion_job_service),
):
    """List all jobs"""
    jobs = ingestion_job_service.list_jobs()
    return JobListResponse(jobs=jobs)


# ========== Tracked Directory Endpoints ==========

@router.post("/tracked", response_model=TrackedDirectoryResponse)
async def add_tracked_directory(
    request: AddTrackedDirectoryRequest,
    directory_sync_service= Depends(get_directory_sync_service),
):
    """Add a directory to be continuously tracked and synced."""
    try:
        tracked_dir = await directory_sync_service.add_tracked_directory(
            directory_path=request.path,
            strategy=request.sync_strategy,
            sync_interval_seconds=request.sync_interval_seconds,
        )
        return TrackedDirectoryResponse(
            id=tracked_dir.id,
            path=tracked_dir.path,
            sync_strategy=tracked_dir.sync_strategy,
            is_active=tracked_dir.is_active,
            last_synced_at=tracked_dir.last_synced_at.isoformat() if tracked_dir.last_synced_at else None,
            last_error=tracked_dir.last_error,
            sync_interval_seconds=tracked_dir.sync_interval_seconds,
            created_at=tracked_dir.created_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add tracked directory: {e}")


@router.get("/tracked", response_model=TrackedDirectoryListResponse)
async def list_tracked_directories(
    directory_sync_service= Depends(get_directory_sync_service),
):
    """List all tracked directories."""
    directories = await directory_sync_service.list_tracked_directories()
    return TrackedDirectoryListResponse(
        directories=[TrackedDirectoryResponse(**d) for d in directories]
    )


@router.get("/tracked/{directory_id}", response_model=TrackedDirectoryResponse)
async def get_tracked_directory(
    directory_id: int,
    directory_sync_service= Depends(get_directory_sync_service),
):
    """Get details of a tracked directory."""
    dir_info = await directory_sync_service.get_tracked_directory(directory_id)
    if not dir_info:
        raise HTTPException(status_code=404, detail="Tracked directory not found")
    return TrackedDirectoryResponse(**dir_info)


@router.delete("/tracked/{directory_id}")
async def remove_tracked_directory(
    directory_id: int,
    directory_sync_service= Depends(get_directory_sync_service),
):
    """Remove a tracked directory."""
    removed = await directory_sync_service.remove_tracked_directory(directory_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Tracked directory not found")
    return {"message": "Tracked directory removed", "directory_id": directory_id}


@router.post("/tracked/{directory_id}/sync", response_model=SyncTriggerResponse)
async def sync_tracked_directory(
    directory_id: int,
    background_tasks: BackgroundTasks,
    directory_sync_service= Depends(get_directory_sync_service),
    ingestion_job_service= Depends(get_ingestion_job_service),
):
    """Manually trigger a sync for a tracked directory in the background."""
    try:
        # Create a job ID for tracking
        job_id = ingestion_job_service.create_job_id()
        ingestion_job_service.init_job(job_id)
        
        # Start sync in background
        background_tasks.add_task(directory_sync_service.sync_directory, directory_id, job_id)
        
        return SyncTriggerResponse(
            job_id=job_id,
            status="pending"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start sync: {e}")
