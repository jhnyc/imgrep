from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from ..embeddings import embed_text_async, embed_image_bytes_async
from ..database import get_all_embeddings
from ..models import Image

router = APIRouter(prefix="/api/search", tags=["search"])


class SearchResult(BaseModel):
    image_id: int
    similarity: float
    thumbnail_url: str


class TextSearchRequest(BaseModel):
    query: str
    top_k: int = 1


class TextSearchResponse(BaseModel):
    results: List[SearchResult]
    total: int


class ImageSearchResponse(BaseModel):
    results: List[SearchResult]
    total: int


def find_similar_images(
    query_embedding: np.ndarray,
    image_embeddings: dict,
    top_k: int = 20
) -> List[tuple[int, float]]:
    """Find top-k similar images by cosine similarity"""
    image_ids = list(image_embeddings.keys())
    embeddings_matrix = np.array([image_embeddings[id] for id in image_ids])

    # Compute similarities
    similarities = cosine_similarity([query_embedding], embeddings_matrix)[0]

    # Get top-k
    top_indices = np.argsort(similarities)[::-1][:top_k]
    return [(int(image_ids[i]), float(similarities[i])) for i in top_indices]


@router.post("/text", response_model=TextSearchResponse)
async def search_by_text(request: TextSearchRequest):
    """Search images by text query"""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Get all embeddings
    image_embeddings = await get_all_embeddings()
    if not image_embeddings:
        return TextSearchResponse(results=[], total=0)

    # Embed query
    query_embedding = await embed_text_async(request.query)
    query_np = np.array(query_embedding)

    # Find similar images
    similar_images = find_similar_images(query_np, image_embeddings, request.top_k)

    # Get thumbnail URLs
    from ..database import AsyncSessionLocal
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        image_ids = [img_id for img_id, _ in similar_images]
        if not image_ids:
            return TextSearchResponse(results=[], total=0)

        result = await session.execute(
            select(Image).where(Image.id.in_(image_ids))
        )
        images = {img.id: img for img in result.scalars().all()}

    results = []
    for img_id, similarity in similar_images:
        img = images.get(img_id)
        if img:
            results.append(SearchResult(
                image_id=img_id,
                similarity=similarity,
                thumbnail_url=f"/api/thumbnails/{img.thumbnail_path}" if img.thumbnail_path else "",
            ))

    return TextSearchResponse(results=results, total=len(results))


@router.post("/image", response_model=ImageSearchResponse)
async def search_by_image(file: UploadFile = File(...), top_k: int = 1):
    """Search images by uploaded image (reverse image search)"""
    # Check file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Read and embed image
    image_bytes = await file.read()
    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    query_embedding = await embed_image_bytes_async(image_bytes)
    query_np = np.array(query_embedding)

    # Get all embeddings
    image_embeddings = await get_all_embeddings()
    if not image_embeddings:
        return ImageSearchResponse(results=[], total=0)

    # Find similar images
    similar_images = find_similar_images(query_np, image_embeddings, top_k)

    # Get thumbnail URLs
    from ..database import AsyncSessionLocal
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        image_ids = [img_id for img_id, _ in similar_images]
        if not image_ids:
            return ImageSearchResponse(results=[], total=0)

        result = await session.execute(
            select(Image).where(Image.id.in_(image_ids))
        )
        images = {img.id: img for img in result.scalars().all()}

    results = []
    for img_id, similarity in similar_images:
        img = images.get(img_id)
        if img:
            results.append(SearchResult(
                image_id=img_id,
                similarity=similarity,
                thumbnail_url=f"/api/thumbnails/{img.thumbnail_path}" if img.thumbnail_path else "",
            ))

    return ImageSearchResponse(results=results, total=len(results))
