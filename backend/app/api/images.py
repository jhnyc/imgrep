from pathlib import Path
from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select, func

from ..database import AsyncSessionLocal
from ..models import Image
from ..constants import DATA_DIR


router = APIRouter(prefix="/api/images", tags=["images"])


class ImageDetails(BaseModel):
    id: int
    file_path: str
    file_name: str
    width: Optional[int]
    height: Optional[int]
    thumbnail_url: str
    cluster_label: Optional[int] = None


class ImageListItem(BaseModel):
    id: int
    file_name: str
    thumbnail_url: str


class ImageListResponse(BaseModel):
    images: List[ImageListItem]
    total: int


@router.get("/list", response_model=ImageListResponse)
async def list_images(
    search: Optional[str] = Query(None, description="Search by filename"),
    sort_by: Literal["name", "newest", "oldest"] = Query("name", description="Sort order"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    """List images with optional filename search and sorting"""
    async with AsyncSessionLocal() as session:
        # Base query
        query = select(Image)
        count_query = select(func.count(Image.id))
        
        # Filter by filename if search provided
        if search:
            search_pattern = f"%{search}%"
            query = query.where(Image.file_path.ilike(search_pattern))
            count_query = count_query.where(Image.file_path.ilike(search_pattern))
        
        # Sorting
        if sort_by == "name":
            query = query.order_by(Image.file_path.asc())
        elif sort_by == "newest":
            query = query.order_by(Image.id.desc())
        elif sort_by == "oldest":
            query = query.order_by(Image.id.asc())
        
        # Pagination
        query = query.offset(offset).limit(limit)
        
        result = await session.execute(query)
        images = result.scalars().all()
        
        count_result = await session.execute(count_query)
        total = count_result.scalar() or 0
        
        return ImageListResponse(
            images=[
                ImageListItem(
                    id=img.id,
                    file_name=Path(img.file_path).name,
                    thumbnail_url=f"/api/thumbnails/{img.thumbnail_path}" if img.thumbnail_path else "",
                )
                for img in images
            ],
            total=total,
        )


@router.get("/{image_id}", response_model=ImageDetails)
async def get_image_details(image_id: int):
    """Get image details by ID"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Image).where(Image.id == image_id))
        image = result.scalar_one_or_none()

        if not image:
            raise HTTPException(status_code=404, detail="Image not found")

        file_path = Path(image.file_path)
        return ImageDetails(
            id=image.id,
            file_path=image.file_path,
            file_name=file_path.name,
            width=image.width,
            height=image.height,
            thumbnail_url=f"/api/thumbnails/{image.thumbnail_path}" if image.thumbnail_path else "",
        )


@router.get("/{image_id}/view")
async def view_original_image(image_id: int):
    """Stream original image file"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Image).where(Image.id == image_id))
        image = result.scalar_one_or_none()

        if not image:
            raise HTTPException(status_code=404, detail="Image not found")

        file_path = Path(image.file_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Original file not found")

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
async def get_thumbnail(thumbnail_path: str):
    """Serve thumbnail image"""
    # Security: validate path is within DATA_DIR to prevent path traversal
    thumb_file = (DATA_DIR / thumbnail_path).resolve()

    # Ensure the resolved path is within DATA_DIR
    try:
        thumb_file.relative_to(DATA_DIR)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if not thumb_file.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    if not thumb_file.is_file():
        raise HTTPException(status_code=404, detail="Not a file")

    return FileResponse(
        thumb_file,
        media_type="image/jpeg",
        cache_max_age=3600 * 24 * 30,  # 30 days
    )
