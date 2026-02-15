from typing import Optional, List

from sqlalchemy import select, func

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.sql import TrackedDirectory, DirectorySnapshot, MerkleNode


class TrackedDirectoryRepository:
    """Repository for TrackedDirectory entity operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, directory_id: int) -> Optional[TrackedDirectory]:
        """Get tracked directory by ID"""
        result = await self.session.execute(
            select(TrackedDirectory).where(TrackedDirectory.id == directory_id)
        )
        return result.scalar_one_or_none()

    async def get_by_path(self, path: str) -> Optional[TrackedDirectory]:
        """Get tracked directory by path"""
        result = await self.session.execute(
            select(TrackedDirectory).where(TrackedDirectory.path == path)
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> List[TrackedDirectory]:
        """List all active tracked directories"""
        result = await self.session.execute(
            select(TrackedDirectory).where(TrackedDirectory.is_active == True)
        )
        return result.scalars().all()

    async def get_file_count(self, directory_id: int, strategy: str) -> int:
        """
        Get file count for a tracked directory based on its sync strategy.

        Args:
            directory_id: The tracked directory ID
            strategy: The sync strategy (snapshot or merkle)

        Returns:
            Number of files tracked
        """
        count = 0
        if strategy == "snapshot":
            count_res = await self.session.execute(
                select(func.count()).select_from(DirectorySnapshot).where(
                    DirectorySnapshot.tracked_directory_id == directory_id
                )
            )
            count = count_res.scalar()
        elif strategy == "merkle":
            count_res = await self.session.execute(
                select(func.count()).select_from(MerkleNode).where(
                    MerkleNode.tracked_directory_id == directory_id,
                    MerkleNode.node_type == "file"
                )
            )
            count = count_res.scalar()

        return count or 0

    async def create(
        self,
        path: str,
        strategy: str,
        sync_interval_seconds: int
    ) -> TrackedDirectory:
        """Create a new tracked directory"""
        tracked_dir = TrackedDirectory(
            path=path,
            sync_strategy=strategy,
            is_active=True,
            sync_interval_seconds=sync_interval_seconds,
        )
        self.session.add(tracked_dir)
        await self.flush()
        await self.refresh(tracked_dir)
        return tracked_dir

    async def update(
        self,
        tracked_dir: TrackedDirectory,
        strategy: str,
        sync_interval_seconds: int
    ) -> TrackedDirectory:
        """Update an existing tracked directory"""
        tracked_dir.is_active = True
        tracked_dir.sync_strategy = strategy
        tracked_dir.sync_interval_seconds = sync_interval_seconds
        await self.flush()
        await self.refresh(tracked_dir)
        return tracked_dir
