from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from ..embeddings import embed_text_async, embed_image_bytes_async
from ..database import AsyncSessionLocal
from ..models import Image
from ..chroma import chroma_manager

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


@router.post("/text", response_model=TextSearchResponse)
async def search_by_text(request: TextSearchRequest):
    """Search images by text query"""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Embed query
    query_embedding = await embed_text_async(request.query)

    # Search in Chroma
    chroma_results = chroma_manager.search_by_vector(query_embedding, request.top_k)
    
    if not chroma_results["ids"] or not chroma_results["ids"][0]:
        return TextSearchResponse(results=[], total=chroma_manager.collection.count())

    image_ids = [int(id_) for id_ in chroma_results["ids"][0]]
    # Distances in Chroma with cosine space are (1 - cosine_similarity)
    # So similarity = 1 - distance
    similarities = [1.0 - float(dist) for dist in chroma_results["distances"][0]]

    # Get thumbnail URLs from SQLite
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(Image).where(Image.id.in_(image_ids))
        )
        images = {img.id: img for img in result.scalars().all()}

    results = []
    for img_id, similarity in zip(image_ids, similarities):
        img = images.get(img_id)
        if img:
            results.append(SearchResult(
                image_id=img_id,
                similarity=similarity,
                thumbnail_url=f"/api/thumbnails/{img.thumbnail_path}" if img.thumbnail_path else "",
            ))

    return TextSearchResponse(
        results=results,
        total=chroma_manager.collection.count()
    )


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

    # Search in Chroma
    chroma_results = chroma_manager.search_by_vector(query_embedding, top_k)
    
    if not chroma_results["ids"] or not chroma_results["ids"][0]:
        return ImageSearchResponse(results=[], total=chroma_manager.collection.count())

    image_ids = [int(id_) for id_ in chroma_results["ids"][0]]
    similarities = [1.0 - float(dist) for dist in chroma_results["distances"][0]]

    # Get thumbnail URLs from SQLite
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(Image).where(Image.id.in_(image_ids))
        )
        images = {img.id: img for img in result.scalars().all()}

    results = []
    for img_id, similarity in zip(image_ids, similarities):
        img = images.get(img_id)
        if img:
            results.append(SearchResult(
                image_id=img_id,
                similarity=similarity,
                thumbnail_url=f"/api/thumbnails/{img.thumbnail_path}" if img.thumbnail_path else "",
            ))

    return ImageSearchResponse(
        results=results,
        total=chroma_manager.collection.count()
    )
