import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, TYPE_CHECKING

from sqlalchemy import select, func, delete
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
        self._batch_size = 12
        self._image_extensions: List[str] = [".jpg", ".jpeg", ".png", ".webp"]
        self._embedding_model = "jina-clip-v2"
        self._vector_store = vector_store
        self._ingestion_job_service = ingestion_job_service

    async def update_settings(
        self, 
        auto_reindex: bool, 
        sync_frequency: str,
        batch_size: Optional[int] = None,
        image_extensions: Optional[List[str]] = None,
        embedding_model: Optional[str] = None
    ) -> None:
        """Update sync settings dynamically."""
        self._sync_enabled = auto_reindex
        
        if batch_size:
            self._batch_size = batch_size
        if image_extensions:
            # Ensure extensions start with dot
            self._image_extensions = [ext if ext.startswith('.') else f".{ext}" for ext in image_extensions]
        if embedding_model:
            self._embedding_model = embedding_model

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
        CHECK_INTERVAL = 10  # Check every 10 seconds
        
        while not self._ensure_stop_event().is_set():
            try:
                if self._sync_enabled:
                    async with AsyncSessionLocal() as session:
                        result = await session.execute(
                            select(TrackedDirectory).where(TrackedDirectory.is_active == True)
                        )
                        directories = result.scalars().all()

                        for tracked_dir in directories:
                            if self._ensure_stop_event().is_set():
                                break

                            if self._should_sync_directory_obj(tracked_dir):
                                print(f"[INFO] Background sync triggered for: {tracked_dir.path}")
                                await self._sync_with_error_handling_obj(tracked_dir)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[ERROR] Error in sync loop: {e}")

            # Shorter sleep to be responsive to stop_event or settings changes
            try:
                await asyncio.sleep(CHECK_INTERVAL)
            except asyncio.CancelledError:
                break

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

            # 1. Clean up images in this directory
            # We match by path prefix
            dir_path_prefix = tracked_dir.path
            if not dir_path_prefix.endswith('/'):
                dir_path_prefix += '/'

            # Find images belonging to this directory
            img_result = await session.execute(
                select(Image).where(Image.file_path.like(f"{dir_path_prefix}%"))
            )
            images = img_result.scalars().all()

            if images:
                image_ids = [img.id for img in images]
                image_id_strs = [str(id_) for id_ in image_ids]
                embedding_ids = [img.embedding_id for img in images if img.embedding_id]
                
                print(f"[INFO] Removing {len(image_ids)} images associated with directory: {tracked_dir.path}")
                
                # 1. Remove from vector store
                try:
                    if self._vector_store:
                        self._vector_store.delete_by_ids(ids=image_id_strs)
                except Exception as e:
                    print(f"[ERROR] Failed to remove images from vector store: {e}")

                # 2. Remove cluster assignments
                from ..models.sql import ClusterAssignment
                await session.execute(
                    delete(ClusterAssignment).where(ClusterAssignment.image_id.in_(image_ids))
                )

                # 3. Remove images
                for img in images:
                    await session.delete(img)
                
                # 4. Remove embeddings
                if embedding_ids:
                    from ..models.sql import Embedding
                    await session.execute(
                        delete(Embedding).where(Embedding.id.in_(embedding_ids))
                    )

            # 2. Clean up strategy-specific data
            strategy = get_sync_strategy(tracked_dir.sync_strategy)
            await strategy.cleanup(tracked_dir, session)

            # 3. Remove the directory record
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
                # 1. Total files expected (from sync strategy tables)
                total_count = 0
                if d.sync_strategy == "snapshot":
                    count_res = await session.execute(
                        select(func.count()).select_from(DirectorySnapshot).where(
                            DirectorySnapshot.tracked_directory_id == d.id
                        )
                    )
                    total_count = count_res.scalar() or 0
                elif d.sync_strategy == "merkle":
                    count_res = await session.execute(
                        select(func.count()).select_from(MerkleNode).where(
                            MerkleNode.tracked_directory_id == d.id,
                            MerkleNode.node_type == "file"
                        )
                    )
                    total_count = count_res.scalar() or 0
                
                # 2. Files actually indexed with embeddings (from Image table)
                path_prefix = d.path if d.path.endswith('/') else d.path + '/'
                indexed_res = await session.execute(
                    select(func.count()).select_from(Image).where(
                        Image.file_path.like(f"{path_prefix}%"),
                        Image.embedding_id.isnot(None)
                    )
                )
                processed_count = indexed_res.scalar() or 0
                
                output.append(self._tracked_dir_to_dict(d, total_count, processed_count))
            
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
            
            # Total count
            total_count = 0
            if tracked_dir.sync_strategy == "snapshot":
                count_res = await session.execute(
                    select(func.count()).select_from(DirectorySnapshot).where(
                        DirectorySnapshot.tracked_directory_id == tracked_dir.id
                    )
                )
                total_count = count_res.scalar() or 0
            elif tracked_dir.sync_strategy == "merkle":
                count_res = await session.execute(
                    select(func.count()).select_from(MerkleNode).where(
                        MerkleNode.tracked_directory_id == tracked_dir.id,
                        MerkleNode.node_type == "file"
                    )
                )
                total_count = count_res.scalar() or 0
            
            # Processed count
            path_prefix = tracked_dir.path if tracked_dir.path.endswith('/') else tracked_dir.path + '/'
            indexed_res = await session.execute(
                select(func.count()).select_from(Image).where(
                    Image.file_path.like(f"{path_prefix}%"),
                    Image.embedding_id.isnot(None)
                )
            )
            processed_count = indexed_res.scalar() or 0
                
            return self._tracked_dir_to_dict(tracked_dir, total_count, processed_count)

    def _tracked_dir_to_dict(self, tracked_dir: TrackedDirectory, total_count: int = 0, processed_count: int = 0) -> dict:
        """Convert TrackedDirectory to dict, including persistent counts."""
        return {
            "id": tracked_dir.id,
            "path": tracked_dir.path,
            "sync_strategy": tracked_dir.sync_strategy,
            "is_active": tracked_dir.is_active,
            "last_synced_at": tracked_dir.last_synced_at.isoformat() if tracked_dir.last_synced_at else None,
            "last_error": tracked_dir.last_error,
            "sync_interval_seconds": tracked_dir.sync_interval_seconds,
            "created_at": tracked_dir.created_at.isoformat(),
            "file_count": total_count,
            "total_count": total_count,
            "processed_count": processed_count,
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
        dir_path_str = tracked_dir.path if tracked_dir.path else "unknown path"
        try:
            if sync_result.deleted:
                await self._handle_deleted_files(tracked_dir, sync_result.deleted, session)

            files_to_index = sync_result.added + sync_result.modified
            if files_to_index:
                await self._index_files(files_to_index, tracked_dir, session, job_id=job_id)

            # Always update sync metadata on success
            tracked_dir.last_synced_at = datetime.now(timezone.utc)
            tracked_dir.last_error = None
            
            await session.commit()
            print(f"[INFO] Sync completed for {dir_path_str}")
        except Exception as e:
            await session.rollback()
            # Use pre-captured path string to avoid greenlet/IO error on expired object
            print(f"[ERROR] Failed to process sync changes for {dir_path_str}: {e}")
            raise

    async def _handle_deleted_files(
        self,
        tracked_dir: TrackedDirectory,
        deleted_relative_paths: List[str],
        session: AsyncSession,
    ) -> None:
        """Handle deleted files - remove from database and Chroma."""
        dir_path = Path(tracked_dir.path)
        for rel_path in deleted_relative_paths:
            # Use absolute path for precise matching
            abs_path = str(dir_path / rel_path)
            
            result = await session.execute(
                select(Image).where(Image.file_path == abs_path)
            )
            images = result.scalars().all()

            for image in images:
                try:
                    if self._vector_store:
                        self._vector_store.delete_by_ids(ids=[str(image.id)])
                except Exception as e:
                    print(f"[ERROR] Failed to delete from Chroma: {e}")

                # Clean up assignments first
                from ..models.sql import ClusterAssignment
                await session.execute(
                    delete(ClusterAssignment).where(ClusterAssignment.image_id == image.id)
                )

                # Capture embedding ID to delete later
                embedding_id = image.embedding_id

                # Delete image to resolve foreign key constraint
                await session.delete(image)
                await session.flush()  # Flush to apply delete

                # Clean up embedding if it exists
                if embedding_id:
                    from ..models.sql import Embedding
                    await session.execute(
                        delete(Embedding).where(Embedding.id == embedding_id)
                    )

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
            batch_size=self._batch_size,
            progress_callback=progress_callback,
        )

        valid_data = [
            (thumbnails_data[i], emb)
            for i, emb in enumerate(embeddings)
            if emb is not None
        ]

        if valid_data:
            valid_thumbnails, valid_embeddings = zip(*valid_data)
            await save_ingested_images(
                session, 
                valid_thumbnails, 
                valid_embeddings, 
                self._vector_store,
                model_name=self._embedding_model
            )

    async def start_background_sync(self) -> None:
        """Start background sync task."""
        if self._sync_task is not None and not self._sync_task.done():
            return

        # Load persisted settings before starting the loop
        await self.load_settings()

        self._ensure_stop_event().clear()
        self._sync_task = asyncio.create_task(self._sync_loop())

    async def stop_background_sync(self) -> None:
        """Stop background sync task."""
        if self._stop_event:
            self._stop_event.set()
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

    async def load_settings(self) -> None:
        """Load sync settings from database."""
        try:
            from ..models.sql import Settings
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Settings).limit(1))
                settings = result.scalar_one_or_none()
                if settings:
                    await self.update_settings(
                        auto_reindex=settings.auto_reindex,
                        sync_frequency=settings.sync_frequency,
                        batch_size=settings.batch_size,
                        image_extensions=settings.image_extensions,
                        embedding_model=settings.embedding_model
                    )
                    print(f"[DEBUG] Loaded background sync settings: enabled={settings.auto_reindex}, freq={settings.sync_frequency}, model={settings.embedding_model}, batch={settings.batch_size}, extensions={settings.image_extensions}")
        except Exception as e:
            print(f"[ERROR] Failed to load sync settings: {e}")

    def _should_sync_directory_obj(self, tracked_dir: TrackedDirectory) -> bool:
        """Check if directory needs sync based on interval."""
        if tracked_dir.last_synced_at is None:
            return True

        # Use directory-specific interval if set, otherwise use global setting
        interval = tracked_dir.sync_interval_seconds or self._sync_interval_seconds
        
        # Ensure last_synced_at has timezone info for comparison
        last_synced = tracked_dir.last_synced_at
        if last_synced.tzinfo is None:
            last_synced = last_synced.replace(tzinfo=timezone.utc)
            
        next_sync = last_synced + timedelta(seconds=interval)
        return datetime.now(timezone.utc) >= next_sync

    async def _sync_with_error_handling_obj(self, tracked_dir: TrackedDirectory) -> None:
        """Sync directory and handle any errors, updating job status."""
        job_id = self._ingestion_job_service.create_job_id()
        self._ingestion_job_service.init_job(job_id)
        if job_id in self._ingestion_job_service._active_jobs:
            self._ingestion_job_service._active_jobs[job_id]["directory_path"] = tracked_dir.path
            self._ingestion_job_service._active_jobs[job_id]["status"] = "processing"

        try:
            strategy = get_sync_strategy(tracked_dir.sync_strategy)
            
            # Use a fresh session for the actual sync to avoid long-lived transaction issues
            # Use a fresh session for the actual sync to avoid long-lived transaction issues
            async with AsyncSessionLocal() as session:
                # Re-fetch tracked_dir in this session
                from sqlalchemy.orm import selectinload
                
                query = select(TrackedDirectory).where(TrackedDirectory.id == tracked_dir.id)
                
                # Eagerly load relationships to avoid implicit lazy load errors during sync
                # Dictionary snapshots and merkle nodes are loaded anyway by strategies, 
                # so identity map ensures we don't double memory usage.
                if tracked_dir.sync_strategy == "merkle":
                    query = query.options(selectinload(TrackedDirectory.merkle_nodes))
                else: 
                    # Default/snapshot
                    query = query.options(selectinload(TrackedDirectory.snapshots))

                result = await session.execute(query)
                db_tracked_dir = result.scalar_one_or_none()
                if not db_tracked_dir:
                    return

                # Pass saved image extensions to strategy
                sync_result = await strategy.sync(db_tracked_dir, session, extensions=self._image_extensions)
                await self._process_sync_changes(db_tracked_dir, sync_result, session, job_id=job_id)
                
                # Success - mark in job service
                if job_id in self._ingestion_job_service._active_jobs:
                    self._ingestion_job_service._active_jobs[job_id]["status"] = "completed"
                    self._ingestion_job_service._active_jobs[job_id]["progress"] = 1.0
        except Exception as e:
            msg = f"Sync failed for {tracked_dir.path}: {str(e)}"
            print(f"[ERROR] {msg}")
            if job_id in self._ingestion_job_service._active_jobs:
                self._ingestion_job_service._active_jobs[job_id]["status"] = "error"
                self._ingestion_job_service._active_jobs[job_id]["errors"].append(str(e))
            
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(TrackedDirectory).where(TrackedDirectory.id == tracked_dir.id)
                )
                db_dir = result.scalar_one_or_none()
                if db_dir:
                    db_dir.last_error = str(e)
                    await session.commit()
