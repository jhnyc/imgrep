from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from ..dependencies import get_image_service
from ..schemas.image import ImageDetails, ImageListResponse


router = APIRouter(prefix="/api/images", tags=["images"])


@router.get("/list", response_model=ImageListResponse)
async def list_images(
    search: Optional[str] = Query(None, description="Search by filename"),
    sort_by: Literal["name", "newest", "oldest"] = Query("name", description="Sort order"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    image_service= Depends(get_image_service),
):
    """List images with optional filename search and sorting"""
    return await image_service.list_images(
        search=search,
        sort_by=sort_by,
        limit=limit,
        offset=offset
    )


@router.get("/{image_id}", response_model=ImageDetails)
async def get_image_details(
    image_id: int,
    image_service= Depends(get_image_service)
):
    """Get image details by ID"""
    return await image_service.get_image_details(image_id)


@router.get("/{image_id}/view")
async def view_original_image(
    image_id: int,
    image_service= Depends(get_image_service)
):
    """Stream original image file"""
    file_path = await image_service.get_original_file_path(image_id)

    # Determine media type
    media_type = "image/jpeg"
    ext = file_path.suffix.lower()
    if ext == ".png":
        media_type = "image/png"
    elif ext == ".webp":
        media_type = "image/webp"
    elif ext == ".gif":
        media_type = "image/gif"
    elif ext in (".jpg", ".jpeg"):
        media_type = "image/jpeg"

    return FileResponse(
        file_path,
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="{file_path.name}"',
        },
    )


@router.get("/thumbnails/{thumbnail_path:path}")
async def get_thumbnail(
    thumbnail_path: str,
    image_service= Depends(get_image_service)
):
    """Serve thumbnail image"""
    thumb_file = await image_service.get_thumbnail_path(thumbnail_path)

    return FileResponse(
        thumb_file,
        media_type="image/jpeg",
        cache_max_age=3600 * 24 * 30,  # 30 days
    )
