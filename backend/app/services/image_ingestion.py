import asyncio
import json
from pathlib import Path
from typing import Any, List, Tuple, Dict, TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.sql import Image, Embedding
from ..core.config import SIGLIP_MODEL_NAME
from ..repositories.image import ImageRepository
from .image import scan_directory, generate_thumbnail, get_image_metadata, compute_file_hash
from .embedding import embed_images_with_progress

if TYPE_CHECKING:
    from .vector_store import VectorStoreService


async def process_directory_for_ingestion(
    session: AsyncSession,
    directory_path: str,
    job_id: str,
    thumbnail_dir: Path,
    vector_store: "VectorStoreService",
    progress_callback: Any = None,
) -> None:
    """
    Process a directory for image ingestion.

    Args:
        session: Database session
        directory_path: Path to the directory to process
        job_id: Job ID for progress tracking
        thumbnail_dir: Directory to store thumbnails
        vector_store: VectorStoreService instance
        progress_callback: Optional callback for progress updates

    Raises:
        PermissionError: If directory access is denied
        Exception: For other processing errors
    """
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
        if progress_callback:
            if asyncio.iscoroutinefunction(progress_callback):
                await progress_callback({
                    "status": "completed",
                    "progress": 1.0,
                    "total": 0,
                    "processed": 0,
                    "errors": [],
                })
            else:
                progress_callback({
                    "status": "completed",
                    "progress": 1.0,
                    "total": 0,
                    "processed": 0,
                    "errors": [],
                })
        return

    if progress_callback:
        if asyncio.iscoroutinefunction(progress_callback):
            await progress_callback({"total": total})
        else:
            progress_callback({"total": total})

    image_repo = ImageRepository(session)

    # Filter out images we already have
    new_images_data = []
    seen_hashes = set()

    for img_path in image_paths:
        try:
            file_hash = compute_file_hash(img_path)

            if file_hash in seen_hashes:
                if progress_callback:
                    if asyncio.iscoroutinefunction(progress_callback):
                        await progress_callback({"processed": len(seen_hashes)})
                    else:
                        progress_callback({"processed": len(seen_hashes)})
                continue

            existing = await image_repo.get_by_hash(file_hash)
            if existing is None:
                new_images_data.append((img_path, file_hash))
                seen_hashes.add(file_hash)
            else:
                if progress_callback:
                    if asyncio.iscoroutinefunction(progress_callback):
                        await progress_callback({"processed": len(seen_hashes)})
                    else:
                        progress_callback({"processed": len(seen_hashes)})
        except Exception as e:
            if progress_callback:
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback({"errors": [f"Error checking {img_path}: {str(e)}"]})
                else:
                    progress_callback({"errors": [f"Error checking {img_path}: {str(e)}"]})

    if not new_images_data:
        if progress_callback:
            if asyncio.iscoroutinefunction(progress_callback):
                await progress_callback({"status": "completed", "progress": 1.0})
            else:
                progress_callback({"status": "completed", "progress": 1.0})
        return

    # Generate thumbnails and collect metadata
    thumbnails_to_embed = []
    for img_path, file_hash in new_images_data:
        try:
            thumb_path = generate_thumbnail(img_path, thumbnail_dir)
            metadata = get_image_metadata(img_path)
            thumbnails_to_embed.append((img_path, file_hash, thumb_path, metadata))
        except Exception as e:
            if progress_callback:
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback({"errors": [f"Error processing {img_path}: {str(e)}"]})
                else:
                    progress_callback({"errors": [f"Error processing {img_path}: {str(e)}"]})

    # Embed images in batches
    image_paths_to_embed = [t[0] for t in thumbnails_to_embed]

    # Create a wrapper callback for embed_images_with_progress that expects async
    async def _embed_callback(data: dict) -> None:
        if progress_callback:
            if asyncio.iscoroutinefunction(progress_callback):
                await progress_callback(data)
            else:
                progress_callback(data)

    embeddings, embed_errors = await embed_images_with_progress(
        image_paths_to_embed,
        batch_size=12,
        progress_callback=_embed_callback,
    )

    if embed_errors and progress_callback:
        if asyncio.iscoroutinefunction(progress_callback):
            await progress_callback({"errors": embed_errors})
        else:
            progress_callback({"errors": embed_errors})

    # Filter out failed embeddings (None keys)
    valid_thumbnails = []
    valid_embeddings = []

    for i, emb in enumerate(embeddings):
        if emb is not None:
            valid_thumbnails.append(thumbnails_to_embed[i])
            valid_embeddings.append(emb)

    if not valid_embeddings:
        if progress_callback:
            if asyncio.iscoroutinefunction(progress_callback):
                await progress_callback({"errors": ["No embeddings generated successfully"]})
            else:
                progress_callback({"errors": ["No embeddings generated successfully"]})
        if progress_callback:
            if asyncio.iscoroutinefunction(progress_callback):
                await progress_callback({"status": "completed", "progress": 1.0})
            else:
                progress_callback({"status": "completed", "progress": 1.0})
        return

    # Save to database and Chroma
    await save_ingested_images(session, valid_thumbnails, valid_embeddings, vector_store)
    await session.commit()


async def save_ingested_images(
    session: AsyncSession,
    thumbnails_data: List[Tuple[Any, str, str, Dict]],
    embeddings: List[List[float]],
    vector_store: "VectorStoreService",
) -> None:
    """
    Save ingested images and embeddings to database and Chroma.

    Args:
        session: Database session
        thumbnails_data: List of (img_path, file_hash, thumb_path, metadata) tuples
        embeddings: List of embedding vectors
        vector_store: VectorStoreService instance
    """
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
            embedding_status="completed",
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

    # Batch add to Chroma before commit (or after flush)
    if chroma_ids:
        vector_store.add_embeddings(
            ids=chroma_ids,
            embeddings=chroma_embeddings,
            metadatas=chroma_metadatas
        )
