import pytest
import asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from app.models.sql import TrackedDirectory, Image, Embedding, Settings
from app.services.directory_sync import DirectorySyncService
from app.services.sync_strategies import SyncResult
from app.core.database import AsyncSessionLocal

@pytest.mark.asyncio
async def test_load_settings_persistence(test_db):
    """Test that DirectorySyncService loads settings from the database on startup."""
    async with AsyncSessionLocal() as session:
        # Create custom settings
        settings = Settings(
            auto_reindex=False,
            sync_frequency="30m"
        )
        session.add(settings)
        await session.commit()

    service = DirectorySyncService()
    # Initially should be defaults
    assert service._sync_enabled is True
    assert service._sync_interval_seconds == 3600

    # Load from DB
    await service.load_settings()
    
    assert service._sync_enabled is False
    assert service._sync_interval_seconds == 1800 # 30 * 60

@pytest.mark.asyncio
async def test_atomic_sync_completion(db_session, tmp_path):
    """Test that last_synced_at is only updated after successful processing."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    
    service = DirectorySyncService()
    tracked_dir = await service.add_tracked_directory(str(images_dir))
    
    # Initial state
    assert tracked_dir.last_synced_at is None
    
    # Mock a sync result with one added file
    sync_result = SyncResult(
        tracked_directory_id=tracked_dir.id,
        added=["img1.jpg"],
        modified=[],
        deleted=[],
        unchanged=0,
        errors=[],
        sync_duration_seconds=0.1,
        strategy_used="snapshot"
    )
    
    # We want to verify that _process_sync_changes updates the timestamp
    async with db_session() as session:
        # Re-fetch tracked_dir
        result = await session.execute(
            select(TrackedDirectory).where(TrackedDirectory.id == tracked_dir.id)
        )
        db_dir = result.scalar_one()
        
        # Call process_sync_changes (it will try to index, but we can mock that or let it skip if file doesn't exist)
        await service._process_sync_changes(db_dir, sync_result, session)
        
        # Check if timestamp was updated
        assert db_dir.last_synced_at is not None
        assert db_dir.last_error is None

@pytest.mark.asyncio
async def test_safe_deletion_with_absolute_paths(db_session, tmp_path):
    """Test that deletion only affects images with exact absolute paths."""
    dir1 = tmp_path / "dir1"
    dir2 = tmp_path / "dir2"
    dir1.mkdir()
    dir2.mkdir()
    
    path1 = dir1 / "shared.jpg"
    path2 = dir2 / "shared.jpg"
    
    service = DirectorySyncService()
    tracked_dir1 = await service.add_tracked_directory(str(dir1))
    
    async with db_session() as session:
        # Create two images with same filename but different paths
        emb1 = Embedding(vector="[0]", model_name="test")
        session.add(emb1)
        await session.flush()
        img1 = Image(file_hash="hash1", file_path=str(path1), embedding_id=emb1.id)
        
        emb2 = Embedding(vector="[0]", model_name="test")
        session.add(emb2)
        await session.flush()
        img2 = Image(file_hash="hash2", file_path=str(path2), embedding_id=emb2.id)
        
        session.add_all([img1, img2])
        await session.commit()
        
        img1_id = img1.id
        img2_id = img2.id

        # Now simulate deleting "shared.jpg" from dir1
        # The new implementation uses absolute paths: dir1 / "shared.jpg"
        await service._handle_deleted_files(tracked_dir1, ["shared.jpg"], session)
        
        # Verify img1 is gone but img2 remains
        res1 = await session.execute(select(Image).where(Image.id == img1_id))
        res2 = await session.execute(select(Image).where(Image.id == img2_id))
        
        assert res1.scalar_one_or_none() is None
        assert res2.scalar_one_or_none() is not None
