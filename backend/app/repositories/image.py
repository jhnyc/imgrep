"""
Image repository - provides a clean interface for image database operations.
"""
from typing import Optional, List, Tuple, Dict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.sql import Image


class ImageRepository:
    """Repository for Image entity operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, image_id: int) -> Optional[Image]:
        """Get image by ID"""
        result = await self.session.execute(
            select(Image).where(Image.id == image_id)
        )
        return result.scalar_one_or_none()

    async def get_by_hash(self, file_hash: str) -> Optional[Image]:
        """Get image by file hash"""
        result = await self.session.execute(
            select(Image).where(Image.file_hash == file_hash)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        search: Optional[str] = None,
        sort_by: str = "name",
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Image], int]:
        """
        List images with optional filtering and pagination.

        Args:
            search: Optional filename search pattern
            sort_by: Sort order - "name", "newest", or "oldest"
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            Tuple of (images list, total count)
        """
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

        result = await self.session.execute(query)
        images = result.scalars().all()

        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        return images, total

    async def get_by_ids(self, image_ids: List[int]) -> Dict[int, Image]:
        """
        Get multiple images by their IDs.

        Args:
            image_ids: List of image IDs

        Returns:
            Dictionary mapping image_id to Image
        """
        if not image_ids:
            return {}

        result = await self.session.execute(
            select(Image).where(Image.id.in_(image_ids))
        )
        return {img.id: img for img in result.scalars().all()}

    async def get_all_ids(self) -> List[int]:
        """Get all image IDs ordered by ID"""
        result = await self.session.execute(
            select(Image.id).order_by(Image.id)
        )
        return [row[0] for row in result.all()]
