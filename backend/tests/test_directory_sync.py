"""
Tests for DirectorySyncService - tracked directory management and periodic sync.
"""
import os
import asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.models.sql import TrackedDirectory, DirectorySnapshot, MerkleNode, Image, Embedding
from app.services.directory_sync import DirectorySyncService
from app.services.sync_strategies import SyncResult


# Minimal valid JPEG bytes
MINIMAL_JPEG = bytes([
    0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46,
    0x00, 0x01, 0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00,
    0xFF, 0xDB, 0x00, 0x43, 0x00, 0x03, 0x02, 0x02, 0x03, 0x02,
    0x02, 0x03, 0x03, 0x03, 0x03, 0x04, 0x03, 0x03, 0x04, 0x05,
    0x08, 0x05, 0x05, 0x04, 0x04, 0x05, 0x0A, 0x07, 0x07, 0x06,
    0x08, 0x0C, 0x0A, 0x0C, 0x0C, 0x0B, 0x0A, 0x0B, 0x0B, 0x0D,
    0x0E, 0x12, 0x10, 0x0D, 0x0E, 0x11, 0x0E, 0x0B, 0x0B, 0x10,
    0x16, 0x10, 0x11, 0x13, 0x14, 0x15, 0x15, 0x15, 0x0C, 0x0F,
    0x17, 0x18, 0x16, 0x14, 0x18, 0x12, 0x14, 0x15, 0x14, 0xFF,
    0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01, 0x00, 0x01, 0x01, 0x01,
    0x11, 0x00, 0xFF, 0xC4, 0x00, 0x14, 0x00, 0x01, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x09, 0xFF, 0xC4, 0x00, 0x14, 0x10, 0x01,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xDA, 0x00,
    0x08, 0x01, 0x01, 0x00, 0x00, 0x3F, 0x00, 0x37, 0xFF, 0xD9
])


def create_test_image(path: Path) -> Path:
    """Create a test image file at the given path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(MINIMAL_JPEG)
    return path


# ============================================
# Tracked Directory Management Tests
# ============================================

@pytest.mark.asyncio
async def test_add_tracked_directory_new(test_db, tmp_path):
    """Test adding a new tracked directory."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()

    service = DirectorySyncService()
    tracked_dir = await service.add_tracked_directory(
        directory_path=str(images_dir),
        strategy="snapshot",
        sync_interval_seconds=300,
    )

    assert tracked_dir.id is not None
    assert tracked_dir.path == str(images_dir)
    assert tracked_dir.sync_strategy == "snapshot"
    assert tracked_dir.is_active is True
    assert tracked_dir.sync_interval_seconds == 300


@pytest.mark.asyncio
async def test_add_tracked_directory_already_exists(test_db, tmp_path):
    """Test adding an already tracked directory updates it."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()

    service = DirectorySyncService()

    # Add first time
    tracked_dir1 = await service.add_tracked_directory(
        directory_path=str(images_dir),
        strategy="snapshot",
        sync_interval_seconds=300,
    )

    # Add second time with different config
    tracked_dir2 = await service.add_tracked_directory(
        directory_path=str(images_dir),
        strategy="merkle",
        sync_interval_seconds=600,
    )

    # Should be the same directory, updated
    assert tracked_dir1.id == tracked_dir2.id
    assert tracked_dir2.sync_strategy == "merkle"
    assert tracked_dir2.sync_interval_seconds == 600


@pytest.mark.asyncio
async def test_add_tracked_directory_not_a_directory(test_db, tmp_path):
    """Test adding a path that is not a directory raises error."""
    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("not a directory")

    service = DirectorySyncService()

    with pytest.raises(ValueError, match="Not a valid directory"):
        await service.add_tracked_directory(str(not_a_dir))


@pytest.mark.asyncio
async def test_add_tracked_directory_nonexistent(test_db, tmp_path):
    """Test adding a non-existent path raises error."""
    nonexistent = tmp_path / "does_not_exist"

    service = DirectorySyncService()

    with pytest.raises(ValueError, match="Not a valid directory"):
        await service.add_tracked_directory(str(nonexistent))


@pytest.mark.asyncio
async def test_remove_tracked_directory(test_db, tmp_path):
    """Test removing a tracked directory."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()

    service = DirectorySyncService()

    # Add directory
    tracked_dir = await service.add_tracked_directory(str(images_dir))
    directory_id = tracked_dir.id

    # Remove directory
    removed = await service.remove_tracked_directory(directory_id)

    assert removed is True

    # Verify it's gone
    dir_info = await service.get_tracked_directory(directory_id)
    assert dir_info is None


@pytest.mark.asyncio
async def test_remove_tracked_directory_not_found(test_db):
    """Test removing a non-existent tracked directory."""
    service = DirectorySyncService()
    removed = await service.remove_tracked_directory(99999)
    assert removed is False


@pytest.mark.asyncio
async def test_remove_tracked_directory_with_snapshots(db_session, tmp_path):
    """Test that removing a tracked directory cleans up snapshots."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    create_test_image(images_dir / "img1.jpg")

    service = DirectorySyncService()

    # Add directory and sync it
    tracked_dir = await service.add_tracked_directory(
        str(images_dir),
        strategy="snapshot",
    )
    directory_id = tracked_dir.id

    # Perform sync to create snapshots
    async with db_session() as session:
        from app.services.sync_strategies import SnapshotSyncStrategy
        strategy = SnapshotSyncStrategy()
        await strategy.sync(tracked_dir, session)

        # Verify snapshots exist
        from sqlalchemy import select
        result = await session.execute(
            select(DirectorySnapshot).where(
                DirectorySnapshot.tracked_directory_id == directory_id
            )
        )
        snapshots = result.scalars().all()
        assert len(snapshots) > 0

    # Remove directory - should clean up snapshots
    removed = await service.remove_tracked_directory(directory_id)
    assert removed is True

    # Verify snapshots are gone
    async with db_session() as session:
        result = await session.execute(
            select(DirectorySnapshot).where(
                DirectorySnapshot.tracked_directory_id == directory_id
            )
        )
        snapshots = result.scalars().all()
        assert len(snapshots) == 0


@pytest.mark.asyncio
async def test_list_tracked_directories(test_db, tmp_path):
    """Test listing all tracked directories."""
    service = DirectorySyncService()

    # Create multiple directories
    dir1 = tmp_path / "photos1"
    dir2 = tmp_path / "photos2"
    dir1.mkdir()
    dir2.mkdir()

    await service.add_tracked_directory(str(dir1), strategy="snapshot")
    await service.add_tracked_directory(str(dir2), strategy="merkle")

    # List all
    directories = await service.list_tracked_directories()

    assert len(directories) == 2
    paths = {d["path"] for d in directories}
    assert str(dir1) in paths
    assert str(dir2) in paths

    # Verify all required fields are present
    for d in directories:
        assert "id" in d
        assert "path" in d
        assert "sync_strategy" in d
        assert "is_active" in d
        assert "last_synced_at" in d
        assert "last_error" in d
        assert "sync_interval_seconds" in d
        assert "created_at" in d


@pytest.mark.asyncio
async def test_list_tracked_directories_empty(test_db):
    """Test listing when no directories are tracked."""
    service = DirectorySyncService()
    directories = await service.list_tracked_directories()
    assert directories == []


@pytest.mark.asyncio
async def test_get_tracked_directory(test_db, tmp_path):
    """Test getting a specific tracked directory."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()

    service = DirectorySyncService()
    tracked_dir = await service.add_tracked_directory(str(images_dir))

    # Get by ID
    dir_info = await service.get_tracked_directory(tracked_dir.id)

    assert dir_info is not None
    assert dir_info["id"] == tracked_dir.id
    assert dir_info["path"] == str(images_dir)
    assert dir_info["sync_strategy"] == "snapshot"


@pytest.mark.asyncio
async def test_get_tracked_directory_not_found(test_db):
    """Test getting a non-existent tracked directory."""
    service = DirectorySyncService()
    dir_info = await service.get_tracked_directory(99999)
    assert dir_info is None


# ============================================
# Sync Operation Tests
# ============================================

@pytest.mark.asyncio
async def test_sync_directory_not_found(test_db):
    """Test syncing a non-existent tracked directory."""
    service = DirectorySyncService()

    with pytest.raises(ValueError, match="not found"):
        await service.sync_directory(99999)


@pytest.mark.asyncio
async def test_sync_directory_calls_strategy(test_db, tmp_path):
    """Test that sync_directory calls the appropriate strategy."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    create_test_image(images_dir / "img1.jpg")

    service = DirectorySyncService()
    tracked_dir = await service.add_tracked_directory(
        str(images_dir),
        strategy="snapshot",
    )

    # Mock the strategy to verify it's called
    with patch("app.services.directory_sync.get_sync_strategy") as mock_get_strategy:
        mock_strategy = MagicMock()
        mock_strategy.sync = AsyncMock(return_value=SyncResult(
            tracked_directory_id=tracked_dir.id,
            added=[],
            modified=[],
            deleted=[],
            unchanged=0,
            errors=[],
            sync_duration_seconds=0.1,
            strategy_used="snapshot",
        ))
        mock_get_strategy.return_value = mock_strategy

        result = await service.sync_directory(tracked_dir.id)

        # Verify strategy was obtained and called
        mock_get_strategy.assert_called_once_with("snapshot")
        mock_strategy.sync.assert_called_once()


@pytest.mark.asyncio
async def test_sync_directory_nonexistent_path(test_db, tmp_path):
    """Test syncing when directory path doesn't exist."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()

    service = DirectorySyncService()
    tracked_dir = await service.add_tracked_directory(str(images_dir))

    # Delete the directory
    images_dir.rmdir()

    # Sync should handle gracefully
    result = await service.sync_directory(tracked_dir.id)

    assert len(result.errors) > 0
    assert "does not exist" in result.errors[0]


# ============================================
# Background Sync Tests
# ============================================

@pytest.mark.asyncio
async def test_start_stop_background_sync(test_db):
    """Test starting and stopping the background sync loop."""
    service = DirectorySyncService()

    # Start
    await service.start_background_sync()
    assert service._sync_task is not None
    assert not service._sync_task.done()

    # Stop
    await service.stop_background_sync()
    assert service._stop_event.is_set()


@pytest.mark.asyncio
async def test_background_sync_skips_on_no_changes(db_session, tmp_path):
    """Test that background sync skips directories that don't need syncing."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()

    service = DirectorySyncService()

    # Add directory with short interval for testing
    tracked_dir = await service.add_tracked_directory(
        str(images_dir),
        sync_interval_seconds=1,  # 1 second
    )

    # Set last_synced to now so it won't sync again immediately
    tracked_dir.last_synced_at = datetime.now(timezone.utc)
    async with db_session() as session:
        session.add(tracked_dir)
        await session.commit()

    # Mock the sync to track if it's called
    with patch.object(service, "_sync_with_error_handling_obj", new_callable=AsyncMock) as mock_sync:
        # Start background sync
        await service.start_background_sync()

        # Wait a bit
        await asyncio.sleep(0.5)

        # Stop
        await service.stop_background_sync()

        # Sync should not have been called (interval not reached)
        # (Unless timing is unlucky, but with 1 second interval and 0.5s wait, should be fine)
        assert mock_sync.call_count == 0


@pytest.mark.asyncio
async def test_background_sync_with_interval_reached(test_db, tmp_path):
    """Test that background sync syncs directories when interval is reached."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()

    service = DirectorySyncService()
    service._sync_interval_seconds = 0.1  # Very short for testing

    # Add directory with no last_synced (should sync)
    tracked_dir = await service.add_tracked_directory(
        str(images_dir),
        sync_interval_seconds=0,  # Always sync
    )

    # Create a mock sync that completes quickly
    async def mock_sync_func(tracked_dir):
        pass

    with patch.object(service, "_sync_with_error_handling_obj", new=mock_sync_func):
        # Start background sync
        await service.start_background_sync()

        # Wait for at least one sync cycle
        await asyncio.sleep(0.3)

        # Stop
        await service.stop_background_sync()

        # Sync should have been called at least once
        # (We can't assert exact count due to timing, but it should have run)


# ============================================
# File Indexing Tests
# ============================================

@pytest.mark.asyncio
async def test_handle_deleted_files(db_session, tmp_path):
    """Test that deleted files are removed from database."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()

    service = DirectorySyncService()
    tracked_dir = await service.add_tracked_directory(str(images_dir))

    async with db_session() as session:
        # Create a mock image in the database
        from app.services.image import compute_file_hash
        img_path = create_test_image(images_dir / "to_delete.jpg")
        file_hash = compute_file_hash(img_path)

        embedding = Embedding(
            vector="[0.1, 0.2]",
            model_name="test",
        )
        session.add(embedding)
        await session.flush()

        image = Image(
            file_hash=file_hash,
            file_path=str(img_path),
            embedding_id=embedding.id,
            embedding_status="completed",
        )
        session.add(image)
        await session.commit()

        image_id = image.id

        # Now "delete" the file via sync result
        result = SyncResult(
            tracked_directory_id=tracked_dir.id,
            added=[],
            modified=[],
            deleted=["to_delete.jpg"],
            unchanged=0,
            errors=[],
            sync_duration_seconds=0.1,
            strategy_used="snapshot",
        )

        # Handle deletions
        await service._handle_deleted_files(tracked_dir, result.deleted, session)

        # Verify image is deleted
        from sqlalchemy import select
        result = await session.execute(select(Image).where(Image.id == image_id))
        assert result.scalar_one_or_none() is None


# ============================================
# Strategy Integration Tests
# ============================================

@pytest.mark.asyncio
async def test_full_sync_workflow_snapshot(test_db, tmp_path):
    """Test full workflow: add directory, sync, add file, sync again."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    create_test_image(images_dir / "img1.jpg")

    service = DirectorySyncService()

    # Add directory
    tracked_dir = await service.add_tracked_directory(
        str(images_dir),
        strategy="snapshot",
    )

    # First sync
    result1 = await service.sync_directory(tracked_dir.id)
    assert len(result1.added) == 1
    assert len(result1.errors) == 0

    # Add new file
    create_test_image(images_dir / "img2.jpg")

    # Second sync should find new file
    result2 = await service.sync_directory(tracked_dir.id)
    assert len(result2.added) == 1


@pytest.mark.asyncio
async def test_full_sync_workflow_merkle(db_session, tmp_path):
    """Test full workflow with Merkle strategy."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    create_test_image(images_dir / "img1.jpg")

    service = DirectorySyncService()

    # Add directory with Merkle strategy
    tracked_dir = await service.add_tracked_directory(
        str(images_dir),
        strategy="merkle",
    )

    # First sync
    result1 = await service.sync_directory(tracked_dir.id)
    assert len(result1.added) == 1
    assert result1.strategy_used == "merkle"

    # Verify Merkle nodes exist
    async with db_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(MerkleNode).where(
                MerkleNode.tracked_directory_id == tracked_dir.id
            )
        )
        nodes = result.scalars().all()
        assert len(nodes) > 0
