"""Tests for directory API endpoints."""
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.ingestion import directory_service

# Helper to access _active_jobs for testing
def get_active_jobs():
    return directory_service._active_jobs


@pytest.mark.asyncio
async def test_process_directory_permission_error(test_db, tmp_path):
    """Test that permission errors are properly exposed in job status."""
    # Create a directory and make it unreadable (on Unix-like systems)
    restricted_dir = tmp_path / "restricted"
    restricted_dir.mkdir()

    try:
        # Remove read permissions
        restricted_dir.chmod(0o000)

        job_id = "test-permission-job"
        thumbnail_dir = tmp_path / "thumbnails"

        # Initialize job
        directory_service.init_job(job_id)

        # Run the job - it should handle the permission error gracefully
        await directory_service.process_directory_job(str(restricted_dir), job_id, thumbnail_dir)

        # Check that the job status reflects the error
        _active_jobs = get_active_jobs()
        assert job_id in _active_jobs
        job_status = _active_jobs[job_id]

        assert job_status["status"] == "error"
        assert len(job_status["errors"]) > 0
        assert any("permission" in err.lower() for err in job_status["errors"])

    finally:
        # Restore permissions for cleanup
        try:
            restricted_dir.chmod(0o755)
        except:
            pass


@pytest.mark.asyncio
async def test_process_directory_not_found(test_db, tmp_path):
    """Test that non-existent directory is handled properly."""
    nonexistent = tmp_path / "does_not_exist"

    job_id = "test-not-found-job"
    thumbnail_dir = tmp_path / "thumbnails"

    # Initialize job
    directory_service.init_job(job_id)

    # This should fail at the directory existence check
    await directory_service.process_directory_job(str(nonexistent), job_id, thumbnail_dir)

    # Job should have error status
    _active_jobs = get_active_jobs()
    assert job_id in _active_jobs
    job_status = _active_jobs[job_id]
    assert job_status["status"] == "error"


@pytest.mark.asyncio
async def test_process_directory_with_images(test_db, tmp_path):
    """Test successful processing of a directory with images."""
    from app.services.image import compute_file_hash

    # Create test images (minimal JPEG)
    images_dir = tmp_path / "images"
    images_dir.mkdir()

    # Create minimal JPEGs with different content (different hashes)
    minimal_jpeg_1 = bytes([
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
        0x00, 0x00, 0x00, 0x00, 0x09, 0xFF, 0xC4, 0x00, 0x14, 0x10,
        0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xDA,
        0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F, 0x00, 0x37, 0xFF,
        0xD9
    ])

    minimal_jpeg_2 = bytes([
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
        0x00, 0x00, 0x00, 0x00, 0x09, 0xFF, 0xC4, 0x00, 0x14, 0x10,
        0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xDA,
        0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F, 0x00, 0x38, 0xFF,  # Changed last byte
        0xD9
    ])

    img1 = images_dir / "test1.jpg"
    img2 = images_dir / "test2.jpg"
    img1.write_bytes(minimal_jpeg_1)
    img2.write_bytes(minimal_jpeg_2)

    job_id = "test-success-job"
    thumbnail_dir = tmp_path / "thumbnails"

    # Initialize job
    directory_service.init_job(job_id)

    # Mock the embedding API, but patch in directory_service
    with patch("app.services.ingestion.embed_images_with_progress", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = ([[0.1, 0.2], [0.3, 0.4]], [])

        # Mock save_ingested_images too since we don't want to rely on real DB/Chroma in this uni test?
        # Actually the test_db fixture sets up DB. But save_ingested_images calls Chroma too.
        # We need to mock Chroma interactions if we don't want to require Chorma running.
        # save_ingested_images imports chroma_manager.
        
        with patch("app.services.ingestion.chroma_manager") as mock_chroma, \
             patch("app.services.ingestion.save_ingested_images", new_callable=AsyncMock) as mock_save:
            
            await directory_service.process_directory_job(str(images_dir), job_id, thumbnail_dir)

            # Check job completed successfully
            _active_jobs = get_active_jobs()
            assert job_id in _active_jobs
            job_status = _active_jobs[job_id]

            assert job_status["status"] == "completed"
            assert job_status["total"] == 2
            assert job_status["progress"] == 1.0
            assert len(job_status["errors"]) == 0
            # Verify the embedding mock was called once
            mock_embed.assert_called_once()
            mock_save.assert_called_once()


@pytest.mark.asyncio
async def test_process_directory_empty(test_db, tmp_path):
    """Test processing an empty directory."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    job_id = "test-empty-job"
    thumbnail_dir = tmp_path / "thumbnails"

    # Initialize job
    directory_service.init_job(job_id)

    await directory_service.process_directory_job(str(empty_dir), job_id, thumbnail_dir)

    # Job should complete with 0 images
    _active_jobs = get_active_jobs()
    assert job_id in _active_jobs
    job_status = _active_jobs[job_id]

    assert job_status["status"] == "completed"
    assert job_status["total"] == 0
    assert job_status["processed"] == 0
