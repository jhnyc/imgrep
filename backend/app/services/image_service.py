from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.image import ImageRepository
from ..schemas.image import ImageDetails, ImageListItem, ImageListResponse
from ..core.config import DATA_DIR


class ImageService:
    """Service for image-related business logic"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.image_repo = ImageRepository(session)

    async def list_images(
        self,
        search: Optional[str] = None,
        sort_by: str = "name",
        limit: int = 100,
        offset: int = 0
    ) -> ImageListResponse:
        """
        List images with optional filename search and sorting.

        Args:
            search: Optional filename search pattern
            sort_by: Sort order - "name", "newest", or "oldest"
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            ImageListResponse with images and total count
        """
        images, total = await self.image_repo.list(
            search=search,
            sort_by=sort_by,
            limit=limit,
            offset=offset
        )

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

    async def get_image_details(self, image_id: int) -> ImageDetails:
        """
        Get image details by ID.

        Args:
            image_id: The image ID

        Returns:
            ImageDetails with image information

        Raises:
            HTTPException: If image not found
        """
        image = await self.image_repo.get_by_id(image_id)

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

    async def get_thumbnail_path(self, thumbnail_path: str) -> Path:
        """
        Get and validate thumbnail file path.

        Args:
            thumbnail_path: The thumbnail path relative to DATA_DIR

        Returns:
            Path to the thumbnail file

        Raises:
            HTTPException: If thumbnail not found or access denied
        """
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

        return thumb_file

    async def get_original_file_path(self, image_id: int) -> Path:
        """
        Get original image file path.

        Args:
            image_id: The image ID

        Returns:
            Path to the original image file

        Raises:
            HTTPException: If image not found or file doesn't exist
        """
        image = await self.image_repo.get_by_id(image_id)

        if not image:
            raise HTTPException(status_code=404, detail="Image not found")

        file_path = Path(image.file_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Original file not found")

        return file_path
