from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from pydantic import BaseModel
import shutil
import uuid
import json
from pathlib import Path

from ..image_processor import (
    scan_directory,
    compute_file_hash,
    generate_thumbnail,
    get_image_metadata,
)
from ..embeddings import embed_images_with_progress
from ..database import AsyncSessionLocal, get_image_by_hash
from ..models import Image, Embedding
from ..constants import THUMBNAILS_DIR, UPLOADS_DIR, ALLOWED_DIRECTORY_PREFIXES, DEFAULT_BATCH_SIZE

router = APIRouter(prefix="/api/directories", tags=["directories"])

# Store progress for active jobs (in production, use Redis or similar)
_active_jobs: dict[str, dict] = {}


class AddDirectoryRequest(BaseModel):
    path: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str  # pending, processing, completed, error
    progress: float
    total: int
    processed: int
    errors: list[str]


async def process_directory_job(
    directory_path: str,
    job_id: str,
    thumbnail_dir: Path,
):
    print(f"[DEBUG] [{job_id}] Starting job for path: {directory_path}")

    _active_jobs[job_id] = {"status": "processing", "progress": 0.0, "total": 0, "processed": 0, "errors": []}

    try:
        # Scan directory
        dir_path = Path(directory_path)

        # Pre-check: verify we can read the directory
        try:
            list(dir_path.iterdir())
        except PermissionError as e:
            raise PermissionError(f"Permission denied accessing '{directory_path}'. macOS may be blocking access to Downloads/Documents. Try moving images to Desktop or a different folder.") from e

        image_paths = scan_directory(dir_path)
        total = len(image_paths)

        if total == 0:
            _active_jobs[job_id] = {
                "status": "completed",
                "progress": 1.0,
                "total": 0,
                "processed": 0,
                "errors": [],
            }
            return

        _active_jobs[job_id]["total"] = total

        async def progress_callback(progress_data: dict):
            _active_jobs[job_id].update(progress_data)

        # Filter out images we already have
        new_images = []
        for img_path in image_paths:
            file_hash = compute_file_hash(img_path)
            existing = await get_image_by_hash(file_hash)
            if existing is None:
                new_images.append(img_path)
            else:
                _active_jobs[job_id]["processed"] += 1

        if not new_images:
            _active_jobs[job_id]["status"] = "completed"
            _active_jobs[job_id]["progress"] = 1.0
            return

        # Generate thumbnails and collect metadata
        thumbnails_to_embed = []
        for img_path in new_images:
            try:
                file_hash = compute_file_hash(img_path)
                thumb_path = generate_thumbnail(img_path, thumbnail_dir)
                metadata = get_image_metadata(img_path)
                thumbnails_to_embed.append((img_path, file_hash, thumb_path, metadata))
            except Exception as e:
                _active_jobs[job_id]["errors"].append(f"Error processing {img_path}: {str(e)}")

        # Embed images in batches
        image_paths_to_embed = [t[0] for t in thumbnails_to_embed]
        embeddings, embed_errors = await embed_images_with_progress(
            image_paths_to_embed,
            batch_size=12,
            progress_callback=progress_callback,
        )

        _active_jobs[job_id]["errors"].extend(embed_errors)

        # Save to database
        async with AsyncSessionLocal() as session:
            for i, (img_path, file_hash, thumb_path, metadata) in enumerate(thumbnails_to_embed):
                if i >= len(embeddings):
                    break

                embedding = Embedding(
                    vector=json.dumps(embeddings[i]),
                    model_name="jina-clip-v2",
                )
                session.add(embedding)
                await session.flush()

                image = Image(
                    file_hash=file_hash,
                    file_path=str(img_path),
                    thumbnail_path=thumb_path,
                    width=metadata.get("width"),
                    height=metadata.get("height"),
                    embedding_id=embedding.id,
                )
                session.add(image)

            await session.commit()

        _active_jobs[job_id]["status"] = "completed"
        _active_jobs[job_id]["progress"] = 1.0

    except Exception as e:
        import traceback
        error_msg = f"{type(e).__name__}: {str(e)}"
        print(f"[ERROR] [{job_id}] Job failed: {error_msg}")
        print(f"[ERROR] [{job_id}] Traceback: {traceback.format_exc()}")
        _active_jobs[job_id] = {
            "status": "error",
            "progress": _active_jobs.get(job_id, {}).get("progress", 0),
            "total": _active_jobs.get(job_id, {}).get("total", 0),
            "processed": _active_jobs.get(job_id, {}).get("processed", 0),
            "errors": [error_msg],
        }


@router.post("/add", response_model=dict)
async def add_directory(request: AddDirectoryRequest, background_tasks: BackgroundTasks):
    """Add a directory to process images from"""
    job_id = str(uuid.uuid4())

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
    _active_jobs[job_id] = {"status": "pending", "progress": 0.0, "total": 0, "processed": 0, "errors": []}

    # Start background job
    background_tasks.add_task(process_directory_job, str(dir_path), job_id, THUMBNAILS_DIR)

    return {"job_id": job_id, "status": "pending"}


@router.post("/upload", response_model=dict)
async def upload_files(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
):
    """Upload files to process"""
    job_id = str(uuid.uuid4())

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
    _active_jobs[job_id] = {"status": "pending", "progress": 0.0, "total": 0, "processed": 0, "errors": []}

    # Start background job on the upload directory
    background_tasks.add_task(process_directory_job, str(upload_dir), job_id, THUMBNAILS_DIR)
    
    return {"job_id": job_id, "status": "pending", "file_count": saved_count}


@router.get("/job/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get status of a directory processing job"""
    if job_id not in _active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job_id,
        **_active_jobs[job_id],
    )


@router.get("/jobs")
async def list_jobs():
    """List all jobs"""
    return {"jobs": [{"job_id": k, **v} for k, v in _active_jobs.items()]}
