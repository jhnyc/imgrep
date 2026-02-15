import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, TYPE_CHECKING

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.sql import TrackedDirectory, Image, DirectorySnapshot, MerkleNode
from ..core.database import AsyncSessionLocal
from ..core.config import THUMBNAILS_DIR, ALLOWED_DIRECTORY_PREFIXES
from .sync_strategies import get_sync_strategy, SyncResult
from .image import generate_thumbnail, get_image_metadata, compute_file_hash
from .embedding import embed_images_with_progress
from .image_ingestion import save_ingested_images

if TYPE_CHECKING:
    from .vector_store import VectorStoreService
    from .ingestion_job import IngestionJobService


class DirectorySyncService:
    """Service for managing tracked directories and periodic synchronization."""

    def __init__(
        self,
        vector_store: Optional["VectorStoreService"] = None,
        ingestion_job_service: Optional["IngestionJobService"] = None,
    ):
        self._sync_task: Optional[asyncio.Task] = None
        self._stop_event: Optional[asyncio.Event] = None  # Lazy initialization
        self._sync_interval_seconds = 3600  # Default 1h
        self._sync_enabled = True
        self._vector_store = vector_store
        self._ingestion_job_service = ingestion_job_service

    async def update_settings(self, auto_reindex: bool, sync_frequency: str) -> None:
        """Update sync settings dynamically."""
        self._sync_enabled = auto_reindex
        
        # Parse frequency string to seconds
        if sync_frequency.endswith("m"):
            self._sync_interval_seconds = int(sync_frequency[:-1]) * 60
        elif sync_frequency.endswith("h"):
            self._sync_interval_seconds = int(sync_frequency[:-1]) * 3600
        elif sync_frequency.endswith("d"):
            self._sync_interval_seconds = int(sync_frequency[:-1]) * 86400
        else:
            self._sync_interval_seconds = 3600 # Default fallback

        # If sync is disabled, we don't need to do anything special, the loop will check the flag
        # If interval changed, the loop will pick it up on next iteration

    def _ensure_stop_event(self) -> asyncio.Event:
        """Ensure the stop event is created (lazy initialization)"""
        if self._stop_event is None:
            self._stop_event = asyncio.Event()
        return self._stop_event

    async def _sync_loop(self) -> None:
        """Main sync loop - periodically check and sync directories."""
        CHECK_INTERVAL = 5  # Check every 5 seconds
        
        while not self._ensure_stop_event().is_set():
            try:
                if self._sync_enabled:
                    directories = await self.list_tracked_directories()

                    for dir_info in directories:
                        if self._ensure_stop_event().is_set():
                            break

                        if self._should_sync_directory(dir_info):
                            await self._sync_with_error_handling(dir_info)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass

            # Shorter sleep to be responsive
            await asyncio.sleep(CHECK_INTERVAL)

    async def add_tracked_directory(
        self,
        directory_path: str,
        strategy: str = "snapshot",
        sync_interval_seconds: int = 300,
    ) -> TrackedDirectory:
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

    async def list_tracked_directories(self) -> List[Dict]:
        """List all tracked directories with file counts."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(TrackedDirectory).where(TrackedDirectory.is_active == True)
            )
            directories = result.scalars().all()
            
            output = []
            for d in directories:
                count = 0
                if d.sync_strategy == "snapshot":
                    count_res = await session.execute(
                        select(func.count()).select_from(DirectorySnapshot).where(
                            DirectorySnapshot.tracked_directory_id == d.id
                        )
                    )
                    count = count_res.scalar()
                elif d.sync_strategy == "merkle":
                    count_res = await session.execute(
                        select(func.count()).select_from(MerkleNode).where(
                            MerkleNode.tracked_directory_id == d.id,
                            MerkleNode.node_type == "file"
                        )
                    )
                    count = count_res.scalar()
                
                output.append(self._tracked_dir_to_dict(d, count))
            
            return output

    async def get_tracked_directory(self, directory_id: int) -> Optional[dict]:
        """Get details of a tracked directory."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(TrackedDirectory).where(TrackedDirectory.id == directory_id)
            )
            tracked_dir = result.scalar_one_or_none()
            if not tracked_dir:
                return None
            
            count = 0
            if tracked_dir.sync_strategy == "snapshot":
                count_res = await session.execute(
                    select(func.count()).select_from(DirectorySnapshot).where(
                        DirectorySnapshot.tracked_directory_id == tracked_dir.id
                    )
                )
                count = count_res.scalar()
            elif tracked_dir.sync_strategy == "merkle":
                count_res = await session.execute(
                    select(func.count()).select_from(MerkleNode).where(
                        MerkleNode.tracked_directory_id == tracked_dir.id,
                        MerkleNode.node_type == "file"
                    )
                )
                count = count_res.scalar()
                
            return self._tracked_dir_to_dict(tracked_dir, count)

    @staticmethod
    def _tracked_dir_to_dict(tracked_dir: TrackedDirectory, file_count: int = 0) -> dict:
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
            "file_count": file_count,
        }

    async def sync_directory(self, directory_id: int, job_id: Optional[str] = None) -> SyncResult:
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
            await self._process_sync_changes(tracked_dir, sync_result, session, job_id=job_id)

            return sync_result

    async def _process_sync_changes(
        self,
        tracked_dir: TrackedDirectory,
        sync_result: SyncResult,
        session: AsyncSession,
        job_id: Optional[str] = None,
    ) -> None:
        """Process changes from sync result - index new/modified images, handle deletions."""
        if not (sync_result.added or sync_result.modified or sync_result.deleted):
            return

        if sync_result.deleted:
            await self._handle_deleted_files(sync_result.deleted, session)

        files_to_index = sync_result.added + sync_result.modified
        if files_to_index:
            await self._index_files(files_to_index, tracked_dir, session, job_id=job_id)

        await session.commit()

    async def _handle_deleted_files(
        self,
        deleted_relative_paths: List[str],
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
                    self._vector_store.collection.delete(ids=[str(image.id)])
                except Exception:
                    pass

                await session.delete(image)

        await session.commit()

    async def _index_files(
        self,
        file_paths: List[str],
        tracked_dir: TrackedDirectory,
        session: AsyncSession,
        job_id: Optional[str] = None,
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

        if job_id:
            self._ingestion_job_service._active_jobs[job_id]["total"] = len(image_paths)

        async def progress_callback(data: dict):
            if job_id:
                 self._ingestion_job_service._active_jobs[job_id].update(data)

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
            await save_ingested_images(valid_thumbnails, valid_embeddings, self._vector_store)

    async def start_background_sync(self) -> None:
        """Start background sync task."""
        if self._sync_task is not None and not self._sync_task.done():
            return

        self._ensure_stop_event().clear()
        self._sync_task = asyncio.create_task(self._sync_loop())

    async def stop_background_sync(self) -> None:
        """Stop background sync task."""
        self._ensure_stop_event().set()
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass


    def _should_sync_directory(self, dir_info: dict) -> bool:
        """Check if directory needs sync based on interval."""
        if dir_info["last_synced_at"] is None:
            return True

        last_synced = datetime.fromisoformat(dir_info["last_synced_at"])
        next_sync = last_synced + timedelta(seconds=dir_info["sync_interval_seconds"])
        return datetime.now(timezone.utc) >= next_sync

    async def _sync_with_error_handling(self, dir_info: dict) -> None:
        """Sync directory and handle any errors, updating job status."""
        job_id = self._ingestion_job_service.create_job_id()
        self._ingestion_job_service.init_job(job_id)
        # Manually set path for job status
        self._ingestion_job_service._active_jobs[job_id]["directory_path"] = dir_info["path"]
        self._ingestion_job_service._active_jobs[job_id]["status"] = "processing"

        try:
            print(f"[DEBUG] Starting sync job {job_id} for {dir_info['path']}")
            await self.sync_directory(dir_info["id"], job_id=job_id)
            
            self._ingestion_job_service._active_jobs[job_id]["status"] = "completed"
            self._ingestion_job_service._active_jobs[job_id]["progress"] = 1.0
        except Exception as e:
            msg = f"Sync failed: {str(e)}"
            self._ingestion_job_service._active_jobs[job_id]["status"] = "error"
            self._ingestion_job_service._active_jobs[job_id]["errors"].append(msg)
            
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(TrackedDirectory).where(TrackedDirectory.id == dir_info["id"])
                )
                tracked_dir = result.scalar_one_or_none()
                if tracked_dir:
                    tracked_dir.last_error = str(e)
                    await session.commit()
