from typing import Optional, List

from sqlalchemy import select, update

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.sql import ClusteringRun


class ClusteringRunRepository:
    """Repository for ClusteringRun entity operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_current_run(
        self,
        strategy: str,
        projection_strategy: str,
        overlap_strategy: str,
        corpus_hash: str
    ) -> Optional[ClusteringRun]:
        """
        Get current clustering run for strategy, projection and overlap if corpus matches.

        Args:
            strategy: Clustering strategy name
            projection_strategy: Projection strategy name
            overlap_strategy: Overlap strategy name
            corpus_hash: Hash of the current image corpus

        Returns:
            ClusteringRun if found, None otherwise
        """
        result = await self.session.execute(
            select(ClusteringRun).where(
                ClusteringRun.strategy == strategy,
                ClusteringRun.projection_strategy == projection_strategy,
                ClusteringRun.overlap_strategy == overlap_strategy,
                ClusteringRun.image_corpus_hash == corpus_hash,
                ClusteringRun.is_current == True
            )
        )
        return result.scalar_one_or_none()

    async def get_all_for_corpus(self, corpus_hash: str) -> List[ClusteringRun]:
        """
        Get all clustering runs for a specific corpus hash.

        Args:
            corpus_hash: Hash of the image corpus

        Returns:
            List of ClusteringRun objects
        """
        result = await self.session.execute(
            select(ClusteringRun).where(
                ClusteringRun.image_corpus_hash == corpus_hash
            )
        )
        return list(result.scalars().all())

    async def set_as_current(
        self,
        run_id: int,
        strategy: str,
        projection_strategy: str,
        overlap_strategy: str
    ) -> None:
        """
        Set a clustering run as current, unsetting others for same strategy/projection/overlap.

        Args:
            run_id: The clustering run ID to set as current
            strategy: Strategy name
            projection_strategy: Projection strategy name
            overlap_strategy: Overlap strategy name
        """
        # Unset previous current runs for the same strategy, projection and overlap
        await self.session.execute(
            update(ClusteringRun)
            .where(
                ClusteringRun.strategy == strategy,
                ClusteringRun.projection_strategy == projection_strategy,
                ClusteringRun.overlap_strategy == overlap_strategy
            )
            .values(is_current=False)
        )

        # Set the new current run
        await self.session.execute(
            update(ClusteringRun)
            .where(ClusteringRun.id == run_id)
            .values(is_current=True)
        )
