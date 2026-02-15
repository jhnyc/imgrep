import json
from typing import Dict, List

from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.sql import Image, Embedding


class EmbeddingRepository:
    """Repository for embedding-related operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_with_images(self) -> Dict[int, List[float]]:
        """
        Get all embeddings with their associated image IDs.

        Returns:
            Dictionary mapping image_id to embedding vector (list of floats)
        """
        result = await self.session.execute(
            select(Image.id, Embedding.vector)
            .join(Embedding)
            .where(Image.embedding_id.isnot(None))
        )
        return {
            row[0]: json.loads(row[1])
            for row in result.all()
        }

    async def get_by_image_id(self, image_id: int) -> List[float]:
        """
        Get embedding for a specific image.

        Args:
            image_id: The image ID

        Returns:
            Embedding vector as list of floats

        Raises:
            ValueError: If image has no embedding
        """
        result = await self.session.execute(
            select(Image).where(Image.id == image_id)
        )
        image = result.scalar_one_or_none()

        if not image or not image.embedding_id:
            raise ValueError(f"Image {image_id} has no embedding")

        result = await self.session.execute(
            select(Embedding).where(Embedding.id == image.embedding_id)
        )
        embedding = result.scalar_one_or_none()

        if not embedding:
            raise ValueError(f"Embedding {image.embedding_id} not found")

        return json.loads(embedding.vector)
