from typing import List, Tuple, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File

from ..services.embedding import embed_text_async, embed_image_bytes_async
from ..core.database import AsyncSessionLocal
from ..services.chroma import chroma_manager
from ..schemas.search import (
    SearchResult,
    TextSearchRequest,
    TextSearchResponse,
    ImageSearchResponse,
)
from ..models.sql import Image, ClusteringRun, ClusterAssignment
from sqlalchemy import select


router = APIRouter(prefix="/api/search", tags=["search"])


async def _execute_vector_search(
    query_embedding: List[float],
    top_k: int,
    strategy: Optional[str] = None,
    projection_strategy: Optional[str] = None,
    overlap_strategy: Optional[str] = None,
) -> Tuple[List[SearchResult], int]:
    """
    Shared logic for text and image search.
    """
    # Search in Chroma
    # Force n_results to be exactly top_k (Chroma might return more if not specified correctly, but manager handles it)
    chroma_results = chroma_manager.search_by_vector(query_embedding, top_k)

    if not chroma_results["ids"] or not chroma_results["ids"][0]:
        return [], chroma_manager.collection.count()

    image_ids = [int(id_) for id_ in chroma_results["ids"][0]]
    # Ensure we only take top_k even if Chroma or logic elsewhere allows more
    image_ids = image_ids[:top_k]

    similarities = [1.0 - float(dist) for dist in chroma_results["distances"][0]]
    similarities = similarities[:top_k]

    results = []
    async with AsyncSessionLocal() as session:
        # Get Image and ClusterAssignment in one go if strategies are provided
        query = select(Image).where(Image.id.in_(image_ids))

        # Mapping for image_id to index to maintain Chroma's order
        id_to_idx = {img_id: i for i, img_id in enumerate(image_ids)}

        # Execute image fetch
        img_result = await session.execute(query)
        images = {img.id: img for img in img_result.scalars().all()}

        # Get coordinates if strategies are provided
        coords = {}
        if strategy and projection_strategy and overlap_strategy:
            coord_query = (
                select(ClusterAssignment)
                .join(ClusteringRun)
                .where(
                    ClusterAssignment.image_id.in_(image_ids),
                    ClusteringRun.is_current == True,
                    ClusteringRun.strategy == strategy,
                    ClusteringRun.projection_strategy == projection_strategy,
                    ClusteringRun.overlap_strategy == overlap_strategy
                )
            )
            coord_result = await session.execute(coord_query)
            coords = {ca.image_id: (ca.x, ca.y) for ca in coord_result.scalars().all()}

        for img_id, similarity in zip(image_ids, similarities):
            img = images.get(img_id)
            if img:
                x, y = coords.get(img_id, (None, None))
                results.append(SearchResult(
                    image_id=img_id,
                    similarity=similarity,
                    thumbnail_url=f"/api/thumbnails/{img.thumbnail_path}" if img.thumbnail_path else "",
                    x=x,
                    y=y
                ))

    return results, chroma_manager.collection.count()


@router.post("/text", response_model=TextSearchResponse)
async def search_by_text(request: TextSearchRequest):
    """Search images by text query"""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Embed query
    query_embedding = await embed_text_async(request.query)

    # Use shared search logic
    results, total = await _execute_vector_search(
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
    top_k: int = 20,
    strategy: Optional[str] = None,
    projection_strategy: Optional[str] = None,
    overlap_strategy: Optional[str] = None,
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

    # Use shared search logic
    results, total = await _execute_vector_search(
        query_embedding,
        top_k,
        strategy=strategy,
        projection_strategy=projection_strategy,
        overlap_strategy=overlap_strategy
    )

    return ImageSearchResponse(results=results, total=total)
