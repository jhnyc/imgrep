"""
Tests for sync strategies - SnapshotSyncStrategy and MerkleSyncStrategy.
"""
import os
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from typing import List

import pytest

from app.models.sql import TrackedDirectory, DirectorySnapshot, MerkleNode, Image
from app.services.sync_strategies import (
    SnapshotSyncStrategy,
    MerkleSyncStrategy,
    SyncResult,
    get_sync_strategy,
)
from app.services.image import compute_file_hash, is_image_path


# Minimal valid JPEG bytes (1x1 pixel)
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


def create_test_image(path: Path, content: bytes = None) -> Path:
    """Create a test image file at the given path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content or MINIMAL_JPEG)
    return path


# ============================================
# SnapshotSyncStrategy Tests
# ============================================

@pytest.mark.asyncio
async def test_snapshot_strategy_first_sync(db_session, tmp_path):
    """Test first sync with no existing snapshots - should add all images."""
    # Create test directory with images
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    create_test_image(images_dir / "img1.jpg")
    create_test_image(images_dir / "img2.jpg")

    # Create tracked directory
    async with db_session() as session:
        tracked_dir = TrackedDirectory(
            path=str(images_dir),
            sync_strategy="snapshot",
            is_active=True,
        )
        session.add(tracked_dir)
        await session.commit()
        await session.refresh(tracked_dir)

        # Run sync
        strategy = SnapshotSyncStrategy()
        result = await strategy.sync(tracked_dir, session)

        # Verify results
        assert result.strategy_used == "snapshot"
        assert len(result.added) == 2
        assert len(result.modified) == 0
        assert len(result.deleted) == 0
        assert len(result.errors) == 0
        assert result.unchanged == 0

        # Verify snapshots were created
        from sqlalchemy import select
        snapshots_result = await session.execute(
            select(DirectorySnapshot).where(
                DirectorySnapshot.tracked_directory_id == tracked_dir.id
            )
        )
        snapshots = snapshots_result.scalars().all()
        assert len(snapshots) == 2

        # Verify tracked directory was updated
        await session.refresh(tracked_dir)
        assert tracked_dir.last_synced_at is not None
        assert tracked_dir.last_error is None


@pytest.mark.asyncio
async def test_snapshot_strategy_no_changes(db_session, tmp_path):
    """Test sync with no changes - should detect all files as unchanged."""
    # Create test directory with images
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    create_test_image(images_dir / "img1.jpg")

    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        tracked_dir = TrackedDirectory(
            path=str(images_dir),
            sync_strategy="snapshot",
            is_active=True,
        )
        session.add(tracked_dir)
        await session.commit()
        await session.refresh(tracked_dir)

        # First sync
        strategy = SnapshotSyncStrategy()
        result1 = await strategy.sync(tracked_dir, session)
        assert len(result1.added) == 1

        # Second sync without changes
        result2 = await strategy.sync(tracked_dir, session)
        assert len(result2.added) == 0
        assert len(result2.modified) == 0
        assert len(result2.deleted) == 0
        assert result2.unchanged == 1


@pytest.mark.asyncio
async def test_snapshot_strategy_new_file(db_session, tmp_path):
    """Test detecting new files after initial sync."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    create_test_image(images_dir / "img1.jpg")

    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        tracked_dir = TrackedDirectory(
            path=str(images_dir),
            sync_strategy="snapshot",
            is_active=True,
        )
        session.add(tracked_dir)
        await session.commit()
        await session.refresh(tracked_dir)

        # First sync
        strategy = SnapshotSyncStrategy()
        result1 = await strategy.sync(tracked_dir, session)
        assert len(result1.added) == 1

        # Add new file
        create_test_image(images_dir / "img2.jpg")

        # Second sync should detect new file
        result2 = await strategy.sync(tracked_dir, session)
        assert len(result2.added) == 1
        assert len(result2.modified) == 0
        assert result2.unchanged == 1


@pytest.mark.asyncio
async def test_snapshot_strategy_deleted_file(db_session, tmp_path):
    """Test detecting deleted files."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    img1 = create_test_image(images_dir / "img1.jpg")
    img2 = create_test_image(images_dir / "img2.jpg")

    async with db_session() as session:
        tracked_dir = TrackedDirectory(
            path=str(images_dir),
            sync_strategy="snapshot",
            is_active=True,
        )
        session.add(tracked_dir)
        await session.commit()
        await session.refresh(tracked_dir)

        # First sync
        strategy = SnapshotSyncStrategy()
        result1 = await strategy.sync(tracked_dir, session)
        assert len(result1.added) == 2

        # Delete a file
        img1.unlink()

        # Second sync should detect deletion
        result2 = await strategy.sync(tracked_dir, session)
        assert len(result2.deleted) == 1
        assert "img1.jpg" in result2.deleted[0]


@pytest.mark.asyncio
async def test_snapshot_strategy_modified_file(db_session, tmp_path):
    """Test detecting modified files (content changes)."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    img1 = create_test_image(images_dir / "img1.jpg")

    async with db_session() as session:
        tracked_dir = TrackedDirectory(
            path=str(images_dir),
            sync_strategy="snapshot",
            is_active=True,
        )
        session.add(tracked_dir)
        await session.commit()
        await session.refresh(tracked_dir)

        # First sync
        strategy = SnapshotSyncStrategy()
        result1 = await strategy.sync(tracked_dir, session)
        assert len(result1.added) == 1

        # Modify file (change content, which changes hash and size)
        modified_jpeg = MINIMAL_JPEG + bytes([0x00, 0x00, 0x00])
        img1.write_bytes(modified_jpeg)

        # Second sync should detect modification
        result2 = await strategy.sync(tracked_dir, session)
        assert len(result2.modified) == 1
        assert len(result2.added) == 0


@pytest.mark.asyncio
async def test_snapshot_strategy_subdirectories(db_session, tmp_path):
    """Test that strategy recursively finds images in subdirectories."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    subdir = images_dir / "subfolder"
    subdir.mkdir()

    create_test_image(images_dir / "root.jpg")
    create_test_image(subdir / "nested.jpg")

    async with db_session() as session:
        tracked_dir = TrackedDirectory(
            path=str(images_dir),
            sync_strategy="snapshot",
            is_active=True,
        )
        session.add(tracked_dir)
        await session.commit()
        await session.refresh(tracked_dir)

        # Sync should find both images
        strategy = SnapshotSyncStrategy()
        result = await strategy.sync(tracked_dir, session)

        assert len(result.added) == 2


@pytest.mark.asyncio
async def test_snapshot_strategy_nonexistent_directory(test_db, tmp_path):
    """Test handling of non-existent directory."""
    nonexistent = tmp_path / "does_not_exist"

    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        tracked_dir = TrackedDirectory(
            path=str(nonexistent),
            sync_strategy="snapshot",
            is_active=True,
        )
        session.add(tracked_dir)
        await session.commit()
        await session.refresh(tracked_dir)

        strategy = SnapshotSyncStrategy()
        result = await strategy.sync(tracked_dir, session)

        assert result.added == []
        assert result.modified == []
        assert result.deleted == []
        assert len(result.errors) > 0
        assert "does not exist" in result.errors[0]


@pytest.mark.asyncio
async def test_snapshot_strategy_cleanup(db_session, tmp_path):
    """Test cleanup removes all snapshots for a directory."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    create_test_image(images_dir / "img1.jpg")

    async with db_session() as session:
        tracked_dir = TrackedDirectory(
            path=str(images_dir),
            sync_strategy="snapshot",
            is_active=True,
        )
        session.add(tracked_dir)
        await session.commit()
        await session.refresh(tracked_dir)

        # Create snapshots via sync
        strategy = SnapshotSyncStrategy()
        await strategy.sync(tracked_dir, session)

        # Verify snapshots exist
        from sqlalchemy import select
        snapshots_result = await session.execute(
            select(DirectorySnapshot).where(
                DirectorySnapshot.tracked_directory_id == tracked_dir.id
            )
        )
        assert snapshots_result.scalars().all()

        # Cleanup should remove snapshots
        await strategy.cleanup(tracked_dir, session)

        snapshots_result = await session.execute(
            select(DirectorySnapshot).where(
                DirectorySnapshot.tracked_directory_id == tracked_dir.id
            )
        )
        assert not snapshots_result.scalars().all()


# ============================================
# MerkleSyncStrategy Tests
# ============================================

@pytest.mark.asyncio
async def test_merkle_strategy_first_sync(db_session, tmp_path):
    """Test first sync with no existing Merkle tree."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    create_test_image(images_dir / "img1.jpg")
    create_test_image(images_dir / "img2.jpg")

    async with db_session() as session:
        tracked_dir = TrackedDirectory(
            path=str(images_dir),
            sync_strategy="merkle",
            is_active=True,
        )
        session.add(tracked_dir)
        await session.commit()
        await session.refresh(tracked_dir)

        strategy = MerkleSyncStrategy()
        result = await strategy.sync(tracked_dir, session)

        assert result.strategy_used == "merkle"
        assert len(result.added) == 2
        assert len(result.modified) == 0
        assert len(result.deleted) == 0
        assert len(result.errors) == 0

        # Verify Merkle nodes were created
        from sqlalchemy import select
        nodes_result = await session.execute(
            select(MerkleNode).where(
                MerkleNode.tracked_directory_id == tracked_dir.id
            )
        )
        nodes = nodes_result.scalars().all()
        # Should have: root node, 2 file nodes = 3 minimum
        assert len(nodes) >= 3


@pytest.mark.asyncio
async def test_merkle_strategy_no_changes(db_session, tmp_path):
    """Test sync with no changes - existing tree matches filesystem."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    create_test_image(images_dir / "img1.jpg")

    async with db_session() as session:
        tracked_dir = TrackedDirectory(
            path=str(images_dir),
            sync_strategy="merkle",
            is_active=True,
        )
        session.add(tracked_dir)
        await session.commit()
        await session.refresh(tracked_dir)

        strategy = MerkleSyncStrategy()

        # First sync
        result1 = await strategy.sync(tracked_dir, session)
        assert len(result1.added) == 1

        # Second sync without changes
        result2 = await strategy.sync(tracked_dir, session)
        assert len(result2.added) == 0


@pytest.mark.asyncio
async def test_merkle_strategy_new_file(db_session, tmp_path):
    """Test detecting new files via Merkle tree comparison."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    create_test_image(images_dir / "img1.jpg")

    async with db_session() as session:
        tracked_dir = TrackedDirectory(
            path=str(images_dir),
            sync_strategy="merkle",
            is_active=True,
        )
        session.add(tracked_dir)
        await session.commit()
        await session.refresh(tracked_dir)

        strategy = MerkleSyncStrategy()

        # First sync
        result1 = await strategy.sync(tracked_dir, session)
        assert len(result1.added) == 1

        # Add new file
        create_test_image(images_dir / "img2.jpg")

        # Second sync should detect new file
        result2 = await strategy.sync(tracked_dir, session)
        assert len(result2.added) == 1


@pytest.mark.asyncio
async def test_merkle_strategy_deleted_file(db_session, tmp_path):
    """Test detecting deleted files via Merkle tree."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    img1 = create_test_image(images_dir / "img1.jpg")

    async with db_session() as session:
        tracked_dir = TrackedDirectory(
            path=str(images_dir),
            sync_strategy="merkle",
            is_active=True,
        )
        session.add(tracked_dir)
        await session.commit()
        await session.refresh(tracked_dir)

        strategy = MerkleSyncStrategy()

        # First sync
        result1 = await strategy.sync(tracked_dir, session)
        assert len(result1.added) == 1

        # Delete file
        img1.unlink()

        # Second sync should detect deletion
        result2 = await strategy.sync(tracked_dir, session)
        assert len(result2.deleted) == 1


@pytest.mark.asyncio
async def test_merkle_strategy_nested_directories(db_session, tmp_path):
    """Test Merkle tree building with nested subdirectories."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    subdir1 = images_dir / "sub1"
    subdir1.mkdir()
    subdir2 = subdir1 / "sub2"
    subdir2.mkdir()

    create_test_image(images_dir / "root.jpg")
    create_test_image(subdir1 / "level1.jpg")
    create_test_image(subdir2 / "level2.jpg")

    async with db_session() as session:
        tracked_dir = TrackedDirectory(
            path=str(images_dir),
            sync_strategy="merkle",
            is_active=True,
        )
        session.add(tracked_dir)
        await session.commit()
        await session.refresh(tracked_dir)

        strategy = MerkleSyncStrategy()
        result = await strategy.sync(tracked_dir, session)

        # Should find all 3 images
        assert len(result.added) == 3

        # Verify tree structure
        from sqlalchemy import select
        from sqlalchemy import func
        nodes_result = await session.execute(
            select(MerkleNode.node_type, func.count(MerkleNode.id))
            .where(MerkleNode.tracked_directory_id == tracked_dir.id)
            .group_by(MerkleNode.node_type)
        )
        node_counts = {row[0]: row[1] for row in nodes_result.all()}

        # Should have directory nodes and file nodes
        assert "file" in node_counts
        assert node_counts["file"] == 3  # 3 images
        assert "directory" in node_counts


@pytest.mark.asyncio
async def test_merkle_strategy_cleanup(db_session, tmp_path):
    """Test cleanup removes Merkle tree for a directory."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    create_test_image(images_dir / "img1.jpg")

    async with db_session() as session:
        tracked_dir = TrackedDirectory(
            path=str(images_dir),
            sync_strategy="merkle",
            is_active=True,
        )
        session.add(tracked_dir)
        await session.commit()
        await session.refresh(tracked_dir)

        strategy = MerkleSyncStrategy()

        # Create tree via sync
        await strategy.sync(tracked_dir, session)

        # Verify nodes exist
        from sqlalchemy import select
        nodes_result = await session.execute(
            select(MerkleNode).where(
                MerkleNode.tracked_directory_id == tracked_dir.id
            )
        )
        assert nodes_result.scalars().all()

        # Cleanup should remove nodes
        await strategy.cleanup(tracked_dir, session)

        nodes_result = await session.execute(
            select(MerkleNode).where(
                MerkleNode.tracked_directory_id == tracked_dir.id
            )
        )
        assert not nodes_result.scalars().all()


# ============================================
# Strategy Factory Tests
# ============================================

def test_get_sync_strategy_snapshot():
    """Test getting snapshot strategy from factory."""
    strategy = get_sync_strategy("snapshot")
    assert isinstance(strategy, SnapshotSyncStrategy)


def test_get_sync_strategy_merkle():
    """Test getting Merkle strategy from factory."""
    strategy = get_sync_strategy("merkle")
    assert isinstance(strategy, MerkleSyncStrategy)


def test_get_sync_strategy_invalid():
    """Test that invalid strategy name raises error."""
    with pytest.raises(ValueError, match="Unknown sync strategy"):
        get_sync_strategy("invalid_strategy")


# ============================================
# SyncResult Tests
# ============================================

def test_sync_result_creation():
    """Test SyncResult dataclass creation."""
    result = SyncResult(
        tracked_directory_id=1,
        added=["path1.jpg", "path2.jpg"],
        modified=["path3.jpg"],
        deleted=["path4.jpg"],
        unchanged=10,
        errors=["error1"],
        sync_duration_seconds=1.5,
        strategy_used="snapshot",
    )

    assert result.tracked_directory_id == 1
    assert len(result.added) == 2
    assert len(result.modified) == 1
    assert len(result.deleted) == 1
    assert result.unchanged == 10
    assert len(result.errors) == 1
    assert result.sync_duration_seconds == 1.5
    assert result.strategy_used == "snapshot"
