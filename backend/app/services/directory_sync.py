"""
Directory sync service - manages tracked directories and syncs them using strategies.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.sql import TrackedDirectory, Image
from ..core.database import AsyncSessionLocal
from ..core.config import THUMBNAILS_DIR, ALLOWED_DIRECTORY_PREFIXES
from .sync_strategies import get_sync_strategy, SyncResult
from .image import generate_thumbnail, get_image_metadata, compute_file_hash
from .embedding import embed_images_with_progress
from .chroma import chroma_manager
from .ingestion import save_ingested_images


class DirectorySyncService:
    """Service for managing tracked directories and periodic synchronization."""

    def __init__(self):
        self._sync_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._sync_interval_seconds = 60

    async def add_tracked_directory(
        self,
        directory_path: str,
        strategy: str = "snapshot",
        sync_interval_seconds: int = 300,
    ) -> TrackedDirectory:
        """Add a new directory to track."""
        dir_path = Path(directory_path).expanduser().resolve()
        self._validate_directory(dir_path)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(TrackedDirectory).where(TrackedDirectory.path == str(dir_path))
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.is_active = True
                existing.sync_strategy = strategy
                existing.sync_interval_seconds = sync_interval_seconds
                await session.commit()
                await session.refresh(existing)
                return existing

            tracked_dir = TrackedDirectory(
                path=str(dir_path),
                sync_strategy=strategy,
                is_active=True,
                sync_interval_seconds=sync_interval_seconds,
            )
            session.add(tracked_dir)
            await session.commit()
            await session.refresh(tracked_dir)
            return tracked_dir

    @staticmethod
    def _validate_directory(dir_path: Path) -> None:
        """Validate directory exists and is within allowed prefixes."""
        if not dir_path.is_dir():
            raise ValueError(f"Not a valid directory: {dir_path}")

        if ALLOWED_DIRECTORY_PREFIXES:
            dir_str = str(dir_path)
            if not any(dir_str.startswith(prefix) for prefix in ALLOWED_DIRECTORY_PREFIXES):
                raise ValueError(
                    f"Directory access denied. Allowed prefixes: {', '.join(ALLOWED_DIRECTORY_PREFIXES)}"
                )

    async def remove_tracked_directory(self, directory_id: int) -> bool:
        """Remove a tracked directory and clean up its data."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(TrackedDirectory).where(TrackedDirectory.id == directory_id)
            )
            tracked_dir = result.scalar_one_or_none()

            if not tracked_dir:
                return False

            strategy = get_sync_strategy(tracked_dir.sync_strategy)
            await strategy.cleanup(tracked_dir, session)

            await session.delete(tracked_dir)
            await session.commit()
            return True

    async def list_tracked_directories(self) -> list[dict]:
        """List all tracked directories."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(TrackedDirectory).where(TrackedDirectory.is_active == True)
            )
            directories = result.scalars().all()
            return [self._tracked_dir_to_dict(d) for d in directories]

    async def get_tracked_directory(self, directory_id: int) -> Optional[dict]:
        """Get details of a tracked directory."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(TrackedDirectory).where(TrackedDirectory.id == directory_id)
            )
            tracked_dir = result.scalar_one_or_none()
            return self._tracked_dir_to_dict(tracked_dir) if tracked_dir else None

    @staticmethod
    def _tracked_dir_to_dict(tracked_dir: TrackedDirectory) -> dict:
        """Convert TrackedDirectory to dict."""
        return {
            "id": tracked_dir.id,
            "path": tracked_dir.path,
            "sync_strategy": tracked_dir.sync_strategy,
            "is_active": tracked_dir.is_active,
            "last_synced_at": tracked_dir.last_synced_at.isoformat() if tracked_dir.last_synced_at else None,
            "last_error": tracked_dir.last_error,
            "sync_interval_seconds": tracked_dir.sync_interval_seconds,
            "created_at": tracked_dir.created_at.isoformat(),
        }

    async def sync_directory(self, directory_id: int) -> SyncResult:
        """Manually trigger a sync for a specific directory."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(TrackedDirectory).where(TrackedDirectory.id == directory_id)
            )
            tracked_dir = result.scalar_one_or_none()

            if not tracked_dir:
                raise ValueError(f"Tracked directory not found: {directory_id}")

            strategy = get_sync_strategy(tracked_dir.sync_strategy)
            sync_result = await strategy.sync(tracked_dir, session)
            await self._process_sync_changes(tracked_dir, sync_result, session)

            return sync_result

    async def _process_sync_changes(
        self,
        tracked_dir: TrackedDirectory,
        sync_result: SyncResult,
        session: AsyncSession,
    ) -> None:
        """Process changes from sync result - index new/modified images, handle deletions."""
        if not (sync_result.added or sync_result.modified or sync_result.deleted):
            return

        if sync_result.deleted:
            await self._handle_deleted_files(sync_result.deleted, session)

        files_to_index = sync_result.added + sync_result.modified
        if files_to_index:
            await self._index_files(files_to_index, tracked_dir, session)

        await session.commit()

    async def _handle_deleted_files(
        self,
        deleted_relative_paths: list[str],
        session: AsyncSession,
    ) -> None:
        """Handle deleted files - remove from database and Chroma."""
        for rel_path in deleted_relative_paths:
            result = await session.execute(
                select(Image).where(Image.file_path.contains(rel_path))
            )
            images = result.scalars().all()

            for image in images:
                try:
                    chroma_manager.collection.delete(ids=[str(image.id)])
                except Exception:
                    pass

                await session.delete(image)

        await session.commit()

    async def _index_files(
        self,
        file_paths: list[str],
        tracked_dir: TrackedDirectory,
        session: AsyncSession,
    ) -> None:
        """Index new/modified files - generate thumbnails and embeddings."""
        thumbnails_data = []
        dir_path = Path(tracked_dir.path)

        for img_path_str in file_paths:
            try:
                img_path = Path(img_path_str)
                if not img_path.exists():
                    continue

                file_hash = compute_file_hash(img_path)
                result = await session.execute(
                    select(Image).where(Image.file_hash == file_hash)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    existing.file_path = str(img_path)
                    continue

                thumb_path = generate_thumbnail(img_path, THUMBNAILS_DIR)
                metadata = get_image_metadata(img_path)
                thumbnails_data.append((img_path, file_hash, thumb_path, metadata))

            except Exception as e:
                tracked_dir.last_error = f"Error indexing {img_path_str}: {e}"

        if not thumbnails_data:
            return

        image_paths = [t[0] for t in thumbnails_data]

        async def progress_callback(_: dict):
            pass

        embeddings, _ = await embed_images_with_progress(
            image_paths,
            batch_size=12,
            progress_callback=progress_callback,
        )

        valid_data = [
            (thumbnails_data[i], emb)
            for i, emb in enumerate(embeddings)
            if emb is not None
        ]

        if valid_data:
            valid_thumbnails, valid_embeddings = zip(*valid_data)
            await save_ingested_images(valid_thumbnails, valid_embeddings)

    async def start_background_sync(self) -> None:
        """Start background sync task."""
        if self._sync_task is not None and not self._sync_task.done():
            return

        self._stop_event.clear()
        self._sync_task = asyncio.create_task(self._sync_loop())

    async def stop_background_sync(self) -> None:
        """Stop background sync task."""
        self._stop_event.set()
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

    async def _sync_loop(self) -> None:
        """Main sync loop - periodically check and sync directories."""
        while not self._stop_event.is_set():
            try:
                directories = await self.list_tracked_directories()

                for dir_info in directories:
                    if self._stop_event.is_set():
                        break

                    if self._should_sync_directory(dir_info):
                        await self._sync_with_error_handling(dir_info)

            except asyncio.CancelledError:
                raise
            except Exception:
                pass

            await asyncio.sleep(self._sync_interval_seconds)

    def _should_sync_directory(self, dir_info: dict) -> bool:
        """Check if directory needs sync based on interval."""
        if dir_info["last_synced_at"] is None:
            return True

        last_synced = datetime.fromisoformat(dir_info["last_synced_at"])
        next_sync = last_synced + timedelta(seconds=dir_info["sync_interval_seconds"])
        return datetime.now(timezone.utc) >= next_sync

    async def _sync_with_error_handling(self, dir_info: dict) -> None:
        """Sync directory and handle any errors."""
        try:
            await self.sync_directory(dir_info["id"])
        except Exception as e:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(TrackedDirectory).where(TrackedDirectory.id == dir_info["id"])
                )
                tracked_dir = result.scalar_one_or_none()
                if tracked_dir:
                    tracked_dir.last_error = str(e)
                    await session.commit()


# Global instance
directory_sync_service = DirectorySyncService()
