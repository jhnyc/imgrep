"""
Cluster repository - provides a clean interface for clustering database operations.
"""
from typing import Optional, List

from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.sql import ClusteringRun, ClusterAssignment, ClusterMetadata


class ClusterRepository:
    """Repository for clustering-related operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_current_run(
        self,
        strategy: str,
        corpus_hash: str
    ) -> Optional[ClusteringRun]:
        """
        Get the current clustering run for a strategy if the corpus matches.

        Args:
            strategy: The clustering strategy name
            corpus_hash: Hash of the current image corpus

        Returns:
            ClusteringRun if found, None otherwise
        """
        result = await self.session.execute(
            select(ClusteringRun).where(
                ClusteringRun.strategy == strategy,
                ClusteringRun.image_corpus_hash == corpus_hash,
                ClusteringRun.is_current == True
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, run_id: int) -> Optional[ClusteringRun]:
        """Get clustering run by ID"""
        result = await self.session.execute(
            select(ClusteringRun).where(ClusteringRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def get_assignments(
        self,
        run_id: int
    ) -> List[ClusterAssignment]:
        """
        Get all cluster assignments for a clustering run.

        Args:
            run_id: The clustering run ID

        Returns:
            List of ClusterAssignment objects
        """
        result = await self.session.execute(
            select(ClusterAssignment).where(
                ClusterAssignment.clustering_run_id == run_id
            )
        )
        return result.scalars().all()

    async def get_assignments_with_images(
        self,
        run_id: int
    ) -> List[tuple[ClusterAssignment, "Image"]]:
        """
        Get cluster assignments with their associated images.

        Args:
            run_id: The clustering run ID

        Returns:
            List of tuples (ClusterAssignment, Image)
        """
        from ..models.sql import Image

        result = await self.session.execute(
            select(ClusterAssignment, Image)
            .join(Image, ClusterAssignment.image_id == Image.id)
            .where(ClusterAssignment.clustering_run_id == run_id)
        )
        return result.all()

    async def get_metadata(
        self,
        run_id: int
    ) -> List[ClusterMetadata]:
        """
        Get cluster metadata for a clustering run.

        Args:
            run_id: The clustering run ID

        Returns:
            List of ClusterMetadata objects
        """
        result = await self.session.execute(
            select(ClusterMetadata).where(
                ClusterMetadata.clustering_run_id == run_id
            )
        )
        return result.scalars().all()

    async def set_current(
        self,
        run_id: int,
        strategy: str
    ) -> None:
        """
        Set a clustering run as current, unsetting others for the same strategy.

        Args:
            run_id: The clustering run ID to set as current
            strategy: The strategy name
        """
        from sqlalchemy import update

        # Unset previous current runs for this strategy
        await self.session.execute(
            update(ClusteringRun)
            .where(ClusteringRun.strategy == strategy)
            .values(is_current=False)
        )

        # Set the new current run
        await self.session.execute(
            update(ClusteringRun)
            .where(ClusteringRun.id == run_id)
            .values(is_current=True)
        )

        await self.session.commit()
