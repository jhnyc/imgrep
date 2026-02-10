import asyncio
import base64
from typing import List, Tuple
from pathlib import Path

import httpx

from .constants import JINA_API_KEY, JINA_API_URL, EMBEDDING_MODEL, DEFAULT_BATCH_SIZE, EMBEDDING_TIMEOUT


async def embed_images_batch_async(image_paths: List[Path], batch_size: int = DEFAULT_BATCH_SIZE) -> List[List[float]]:
    """
    Batch embed images using Jina CLIP-v2.
    Processes in batches to avoid API limits.
    """
    all_embeddings = []

    async with httpx.AsyncClient(timeout=EMBEDDING_TIMEOUT) as client:
        for i in range(0, len(image_paths), batch_size):
            batch = image_paths[i:i + batch_size]
            embeddings = await _embed_single_batch(client, batch)
            all_embeddings.extend(embeddings)

    return all_embeddings


async def _embed_single_batch(client: httpx.AsyncClient, image_paths: List[Path]) -> List[List[float]]:
    """Embed a single batch of images"""
    # Prepare inputs with base64 encoded images
    inputs = []
    for path in image_paths:
        with open(path, "rb") as f:
            image_bytes = f.read()
            image_b64 = base64.b64encode(image_bytes).decode()
            inputs.append({"image": image_b64})

    response = await client.post(
        JINA_API_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {JINA_API_KEY}"
        },
        json={"model": EMBEDDING_MODEL, "input": inputs}
    )
    response.raise_for_status()
    data = response.json()

    # Results are returned in order
    return [item["embedding"] for item in data["data"]]


async def embed_text_async(text: str) -> List[float]:
    """Embed text query for search"""
    async with httpx.AsyncClient(timeout=EMBEDDING_TIMEOUT) as client:
        response = await client.post(
            JINA_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {JINA_API_KEY}"
            },
            json={"model": EMBEDDING_MODEL, "input": [{"text": text}]}
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]


async def embed_image_bytes_async(image_bytes: bytes) -> List[float]:
    """Embed uploaded image bytes for reverse image search"""
    image_b64 = base64.b64encode(image_bytes).decode()
    async with httpx.AsyncClient(timeout=EMBEDDING_TIMEOUT) as client:
        response = await client.post(
            JINA_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {JINA_API_KEY}"
            },
            json={"model": EMBEDDING_MODEL, "input": [{"image": image_b64}]}
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]


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
    embeddings = [None] * len(image_paths)
    errors = []
    progress = EmbeddingProgress(len(image_paths))

    async with httpx.AsyncClient(timeout=EMBEDDING_TIMEOUT) as client:
        for i in range(0, len(image_paths), batch_size):
            batch_end = min(i + batch_size, len(image_paths))
            batch = image_paths[i:batch_end]
            batch_indices = list(range(i, batch_end))

            try:
                batch_embeddings = await _embed_single_batch(client, batch)
                for idx, emb in zip(batch_indices, batch_embeddings):
                    embeddings[idx] = emb
                progress.update(len(batch))
            except Exception as e:
                error_msg = f"Batch {i}-{batch_end-1}: {str(e)}"
                errors.append(error_msg)
                progress.add_error(error_msg)
                # Fill with None for failed batch
                for idx in batch_indices:
                    embeddings[idx] = None

            if progress_callback:
                await progress_callback(progress.to_dict())

    # Filter out None embeddings
    valid_embeddings = [e for e in embeddings if e is not None]
    return valid_embeddings, errors
