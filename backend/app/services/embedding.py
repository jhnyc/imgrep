"""
Embedding service - uses local SigLIP model for embeddings.
No API key required.
"""
import asyncio
from functools import lru_cache
from typing import List, Tuple
from pathlib import Path

from ..core.config import DEFAULT_BATCH_SIZE, SIGLIP_MODEL_NAME, SIGLIP_DEVICE


# =============================================================================
# SigLIP Local Embedding
# =============================================================================

def _siglip_embed_images_batch(image_paths: List[Path], batch_size: int = DEFAULT_BATCH_SIZE) -> List[List[float]]:
    """Batch embed images using local SigLIP model"""
    from .embeddings.siglip import get_siglip_embedder

    embedder = get_siglip_embedder()
    all_embeddings = []

    # Process in batches to avoid memory issues
    for i in range(0, len(image_paths), batch_size):
        batch = image_paths[i:i + batch_size]
        embeddings = embedder.embed_images_batch(batch)
        all_embeddings.extend(embeddings)

    return all_embeddings


def _siglip_embed_text(text: str) -> List[float]:
    """Embed text query using local SigLIP model"""
    from .embeddings.siglip import get_siglip_embedder

    embedder = get_siglip_embedder()
    return embedder.embed_text(text)


def _siglip_embed_image_bytes(image_bytes: bytes) -> List[float]:
    """Embed uploaded image bytes using local SigLIP model"""
    from .embeddings.siglip import get_siglip_embedder

    embedder = get_siglip_embedder()
    return embedder.embed_image(image_bytes)


# =============================================================================
# Public API
# =============================================================================

async def embed_images_batch_async(image_paths: List[Path], batch_size: int = DEFAULT_BATCH_SIZE) -> List[List[float]]:
    """
    Batch embed images using local SigLIP model.
    Processes in batches to avoid memory issues.
    """
    # Run in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _siglip_embed_images_batch, image_paths, batch_size)


async def embed_text_async(text: str) -> List[float]:
    """Embed text query for search using local SigLIP model"""
    # Run in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _siglip_embed_text, text)


async def embed_image_bytes_async(image_bytes: bytes) -> List[float]:
    """Embed uploaded image bytes for reverse image search using local SigLIP model"""
    # Run in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _siglip_embed_image_bytes, image_bytes)


# =============================================================================
# Progress Tracking
# =============================================================================

class EmbeddingProgress:
    """Progress tracker for embedding operations"""
    def __init__(self, total: int):
        self.total = total
        self.processed = 0
        self.errors = []

    def update(self, count: int = 1):
        self.processed += count

    def add_error(self, error: str):
        self.errors.append(error)

    @property
    def progress(self) -> float:
        return self.processed / self.total if self.total > 0 else 1.0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "processed": self.processed,
            "progress": self.progress,
            "errors": self.errors[-10:],
        }


async def embed_images_with_progress(
    image_paths: List[Path],
    batch_size: int = DEFAULT_BATCH_SIZE,
    progress_callback = None
) -> Tuple[List[List[float]], List[str]]:
    """
    Embed images with progress tracking.
    Returns (embeddings, error_messages).
    """
    from .embeddings.siglip import get_siglip_embedder

    embeddings = [None] * len(image_paths)
    errors = []
    progress = EmbeddingProgress(len(image_paths))

    embedder = get_siglip_embedder()
    for i in range(0, len(image_paths), batch_size):
        batch_end = min(i + batch_size, len(image_paths))
        batch = image_paths[i:batch_end]
        batch_indices = list(range(i, batch_end))

        try:
            # Run embedding in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            batch_embeddings = await loop.run_in_executor(None, embedder.embed_images_batch, batch)
            
            for idx, emb in enumerate(batch_embeddings):
                embeddings[batch_indices[idx]] = emb
            progress.update(len(batch))
        except Exception as e:
            error_msg = f"Batch {i}-{batch_end-1}: {str(e)}"
            errors.append(error_msg)
            progress.add_error(error_msg)
            
            # Fill with None for failed batch is not needed as we initialized with None, 
            # but we need to update progress for failed items too? 
            # Actually if it failed, we usually just skip them.
            # But we might want to update progress count even on failure so the bar moves?
            progress.update(len(batch))  # Mark as processed (even if failed)

        if progress_callback:
            # Add small yield to ensure checking for cancellation/other tasks
            await asyncio.sleep(0)
            await progress_callback(progress.to_dict())

    # Return all embeddings (including None for failures) to maintain alignment
    return embeddings, errors


# =============================================================================
# Backend Info
# =============================================================================

async def get_embedding_info() -> dict:
    """Get information about the embedding backend"""
    from .embeddings.siglip import get_siglip_embedder

    embedder = get_siglip_embedder()
    return {
        "backend": "siglip",
        "model": embedder.model_name,
        "embedding_dim": embedder.embedding_dim,
        "type": "local",
    }


def get_backend() -> str:
    """Get the embedding backend (always siglip now)"""
    return "siglip"


def is_jina_backend() -> bool:
    """Check if using Jina API backend (always False now)"""
    return False


def is_siglip_backend() -> bool:
    """Check if using SigLIP local backend (always True now)"""
    return True
