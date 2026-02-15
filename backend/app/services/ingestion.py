"""
Ingestion service - handles directory processing and image ingestion.
Combines DirectoryService and save_ingested_images functionality.
"""
import json
import uuid
from pathlib import Path
from typing import Dict, Any, List, Tuple

from ..models.sql import Image, Embedding
from ..core.database import AsyncSessionLocal, get_image_by_hash
from ..services.image import (
    scan_directory,
    compute_file_hash,
    generate_thumbnail,
    get_image_metadata,
)
from ..services.embedding import embed_images_with_progress
from ..services.chroma import chroma_manager


class DirectoryService:
    """Service for managing directory processing jobs"""

    def __init__(self):
        # Store progress for active jobs (in production, use Redis or similar)
        self._active_jobs: Dict[str, Dict[str, Any]] = {}

    def create_job_id(self) -> str:
        return str(uuid.uuid4())

    def init_job(self, job_id: str):
        self._active_jobs[job_id] = {
            "status": "pending",
            "progress": 0.0,
            "total": 0,
            "processed": 0,
            "errors": [],
        }

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        return self._active_jobs.get(job_id)

    def list_jobs(self) -> List[Dict[str, Any]]:
        return [{"job_id": k, **v} for k, v in self._active_jobs.items()]

    async def process_directory_job(
        self,
        directory_path: str,
        job_id: str,
        thumbnail_dir: Path,
    ):
        print(f"[DEBUG] [{job_id}] Starting job for for path: {directory_path}")

        self._active_jobs[job_id] = {
            "status": "processing",
            "progress": 0.0,
            "total": 0,
            "processed": 0,
            "errors": [],
        }

        try:
            # Scan directory
            dir_path = Path(directory_path)

            # Pre-check: verify we can read the directory
            try:
                list(dir_path.iterdir())
            except PermissionError as e:
                raise PermissionError(
                    f"Permission denied accessing '{directory_path}'. macOS may be blocking access to Downloads/Documents. Try moving images to Desktop or a different folder."
                ) from e

            image_paths = scan_directory(dir_path)
            total = len(image_paths)

            if total == 0:
                self._active_jobs[job_id].update({
                    "status": "completed",
                    "progress": 1.0,
                    "total": 0,
                    "processed": 0,
                    "errors": [],
                })
                return

            self._active_jobs[job_id]["total"] = total

            async def progress_callback(progress_data: dict):
                self._active_jobs[job_id].update(progress_data)

            # Filter out images we already have
            new_images_data = []
            seen_hashes = set()
            
            for img_path in image_paths:
                try:
                    file_hash = compute_file_hash(img_path)
                    
                    if file_hash in seen_hashes:
                        self._active_jobs[job_id]["processed"] += 1
                        continue

                    existing = await get_image_by_hash(file_hash)
                    if existing is None:
                        new_images_data.append((img_path, file_hash))
                        seen_hashes.add(file_hash)
                    else:
                        self._active_jobs[job_id]["processed"] += 1
                except Exception as e:
                    self._active_jobs[job_id]["errors"].append(
                        f"Error checking {img_path}: {str(e)}"
                    )

            if not new_images_data:
                self._active_jobs[job_id]["status"] = "completed"
                self._active_jobs[job_id]["progress"] = 1.0
                return

            # Generate thumbnails and collect metadata
            thumbnails_to_embed = []
            for img_path, file_hash in new_images_data:
                try:
                    thumb_path = generate_thumbnail(img_path, thumbnail_dir)
                    metadata = get_image_metadata(img_path)
                    thumbnails_to_embed.append((img_path, file_hash, thumb_path, metadata))
                except Exception as e:
                    self._active_jobs[job_id]["errors"].append(
                        f"Error processing {img_path}: {str(e)}"
                    )

            # Embed images in batches
            image_paths_to_embed = [t[0] for t in thumbnails_to_embed]
            embeddings, embed_errors = await embed_images_with_progress(
                image_paths_to_embed,
                batch_size=12,
                progress_callback=progress_callback,
            )

            self._active_jobs[job_id]["errors"].extend(embed_errors)

            # Filter out failed embeddings (None keys)
            valid_thumbnails = []
            valid_embeddings = []
            
            for i, emb in enumerate(embeddings):
                if emb is not None:
                    valid_thumbnails.append(thumbnails_to_embed[i])
                    valid_embeddings.append(emb)
            
            if not valid_embeddings:
                if not self._active_jobs[job_id]["errors"]:
                     self._active_jobs[job_id]["errors"].append("No embeddings generated successfully")
                self._active_jobs[job_id]["status"] = "completed" # or error? partial success is completed usually
                self._active_jobs[job_id]["progress"] = 1.0
                return

            # Save to database and Chroma
            await save_ingested_images(valid_thumbnails, valid_embeddings)

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


async def save_ingested_images(
    thumbnails_data: List[Tuple[Any, str, str, dict]],
    embeddings: List[List[float]]
) -> None:
    """Save ingested images and embeddings to database and Chroma"""
    from ..core.config import SIGLIP_MODEL_NAME

    async with AsyncSessionLocal() as session:
        chroma_ids = []
        chroma_embeddings = []
        chroma_metadatas = []

        for i, (img_path, file_hash, thumb_path, metadata) in enumerate(thumbnails_data):
            if i >= len(embeddings):
                break

            embedding = Embedding(
                vector=json.dumps(embeddings[i]),
                model_name=SIGLIP_MODEL_NAME,
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
                embedding_status="completed",  # Successfully embedded
            )
            session.add(image)
            await session.flush()  # Flush to get image.id

            # Prepare for Chroma
            chroma_ids.append(str(image.id))
            chroma_embeddings.append(embeddings[i])
            chroma_metadatas.append({
                "file_hash": file_hash,
                "file_path": str(img_path)
            })

        await session.commit()

        # Batch add to Chroma after commit
        if chroma_ids:
            chroma_manager.add_embeddings(
                ids=chroma_ids,
                embeddings=chroma_embeddings,
                metadatas=chroma_metadatas
            )


# Global instance
directory_service = DirectoryService()
