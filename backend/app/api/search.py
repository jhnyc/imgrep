from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Query

from ..services.embedding import embed_text_async, embed_image_bytes_async
from ..dependencies import get_search_service
from ..schemas.search import (
    SearchResult,
    TextSearchRequest,
    TextSearchResponse,
    ImageSearchResponse,
)


router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("/text", response_model=TextSearchResponse)
async def search_by_text(
    request: TextSearchRequest,
    search_service= Depends(get_search_service)
):
    """Search images by text query"""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Embed query
    query_embedding = await embed_text_async(request.query)

    # Use search service
    results, total = await search_service.search_by_vector(
        query_embedding,
        request.top_k,
        strategy=request.strategy,
        projection_strategy=request.projection_strategy,
        overlap_strategy=request.overlap_strategy
    )

    return TextSearchResponse(results=results, total=total)


@router.post("/image", response_model=ImageSearchResponse)
async def search_by_image(
    file: UploadFile = File(...),
    top_k: int = Query(20),
    strategy: Optional[str] = None,
    projection_strategy: Optional[str] = None,
    overlap_strategy: Optional[str] = None,
    search_service= Depends(get_search_service)
):
    """Search images by uploaded image (reverse image search)"""
    # Check file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Read and embed image
    image_bytes = await file.read()
    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    query_embedding = await embed_image_bytes_async(image_bytes)

    # Use search service
    results, total = await search_service.search_by_vector(
        query_embedding,
        top_k,
        strategy=strategy,
        projection_strategy=projection_strategy,
        overlap_strategy=overlap_strategy
    )

    return ImageSearchResponse(results=results, total=total)
