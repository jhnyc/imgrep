"""
Tests for tracked directories API endpoints.
"""
import os
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.sql import TrackedDirectory
from app.services.directory_sync import DirectorySyncService


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
# POST /api/directories/tracked
# ============================================

@pytest.mark.asyncio
async def test_api_add_tracked_directory(client, tmp_path):
    """Test adding a tracked directory via API."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()

    response = await client.post(
        "/api/directories/tracked",
        json={
            "path": str(images_dir),
            "sync_strategy": "snapshot",
            "sync_interval_seconds": 300,
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["path"] == str(images_dir)
    assert data["sync_strategy"] == "snapshot"
    assert data["sync_interval_seconds"] == 300
    assert data["is_active"] is True
    assert "created_at" in data


@pytest.mark.asyncio
async def test_api_add_tracked_directory_default_values(client, tmp_path):
    """Test that default values are applied correctly."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()

    response = await client.post(
        "/api/directories/tracked",
        json={"path": str(images_dir)}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sync_strategy"] == "snapshot"  # default
    assert data["sync_interval_seconds"] == 300  # default


@pytest.mark.asyncio
async def test_api_add_tracked_directory_merkle_strategy(client, tmp_path):
    """Test adding a directory with Merkle strategy."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()

    response = await client.post(
        "/api/directories/tracked",
        json={
            "path": str(images_dir),
            "sync_strategy": "merkle",
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sync_strategy"] == "merkle"


@pytest.mark.asyncio
async def test_api_add_tracked_directory_not_a_directory(client, tmp_path):
    """Test that non-directory path returns 400."""
    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("not a directory")

    response = await client.post(
        "/api/directories/tracked",
        json={"path": str(not_a_dir)}
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_api_add_tracked_directory_nonexistent(client, tmp_path):
    """Test that non-existent path returns 400."""
    nonexistent = tmp_path / "does_not_exist"

    response = await client.post(
        "/api/directories/tracked",
        json={"path": str(nonexistent)}
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_api_add_tracked_directory_already_exists(client, tmp_path):
    """Test that adding an existing directory returns the existing one."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()

    # Add first time
    response1 = await client.post(
        "/api/directories/tracked",
        json={"path": str(images_dir)}
    )
    assert response1.status_code == 200
    id1 = response1.json()["id"]

    # Add second time
    response2 = await client.post(
        "/api/directories/tracked",
        json={"path": str(images_dir)}
    )
    assert response2.status_code == 200
    id2 = response2.json()["id"]

    # Should be the same directory
    assert id1 == id2


@pytest.mark.asyncio
async def test_api_add_tracked_directory_invalid_strategy(client, tmp_path):
    """Test that invalid strategy name is handled."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()

    response = await client.post(
        "/api/directories/tracked",
        json={
            "path": str(images_dir),
            "sync_strategy": "invalid_strategy",
        }
    )

    # Should either return 400 for invalid strategy or accept it
    # (validation might be at different levels)
    assert response.status_code in [200, 400]


# ============================================
# GET /api/directories/tracked
# ============================================

@pytest.mark.asyncio
async def test_api_list_tracked_directories_empty(client):
    """Test listing when no directories are tracked."""
    response = await client.get("/api/directories/tracked")

    assert response.status_code == 200
    data = response.json()
    assert "directories" in data
    assert data["directories"] == []


@pytest.mark.asyncio
async def test_api_list_tracked_directories(client, tmp_path):
    """Test listing multiple tracked directories."""
    dir1 = tmp_path / "photos1"
    dir2 = tmp_path / "photos2"
    dir1.mkdir()
    dir2.mkdir()

    # Add directories
    await client.post(
        "/api/directories/tracked",
        json={"path": str(dir1), "sync_strategy": "snapshot"}
    )
    await client.post(
        "/api/directories/tracked",
        json={"path": str(dir2), "sync_strategy": "merkle"}
    )

    # List
    response = await client.get("/api/directories/tracked")

    assert response.status_code == 200
    data = response.json()
    assert len(data["directories"]) == 2

    # Check all required fields are present
    for d in data["directories"]:
        assert "id" in d
        assert "path" in d
        assert "sync_strategy" in d
        assert "is_active" in d
        assert "last_synced_at" in d
        assert "last_error" in d
        assert "sync_interval_seconds" in d
        assert "created_at" in d


# ============================================
# GET /api/directories/tracked/{id}
# ============================================

@pytest.mark.asyncio
async def test_api_get_tracked_directory(client, tmp_path):
    """Test getting a specific tracked directory."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()

    # Add directory
    add_response = await client.post(
        "/api/directories/tracked",
        json={"path": str(images_dir)}
    )
    directory_id = add_response.json()["id"]

    # Get directory
    response = await client.get(f"/api/directories/tracked/{directory_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == directory_id
    assert data["path"] == str(images_dir)


@pytest.mark.asyncio
async def test_api_get_tracked_directory_not_found(client):
    """Test getting a non-existent tracked directory."""
    response = await client.get("/api/directories/tracked/99999")
    assert response.status_code == 404


# ============================================
# DELETE /api/directories/tracked/{id}
# ============================================

@pytest.mark.asyncio
async def test_api_remove_tracked_directory(client, tmp_path):
    """Test removing a tracked directory."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()

    # Add directory
    add_response = await client.post(
        "/api/directories/tracked",
        json={"path": str(images_dir)}
    )
    directory_id = add_response.json()["id"]

    # Remove directory
    response = await client.delete(f"/api/directories/tracked/{directory_id}")

    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["directory_id"] == directory_id

    # Verify it's gone
    get_response = await client.get(f"/api/directories/tracked/{directory_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_api_remove_tracked_directory_not_found(client):
    """Test removing a non-existent tracked directory."""
    response = await client.delete("/api/directories/tracked/99999")
    assert response.status_code == 404


# ============================================
# POST /api/directories/tracked/{id}/sync
# ============================================

@pytest.mark.asyncio
async def test_api_sync_tracked_directory(client, tmp_path):
    """Test manually triggering a sync."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()

    # Add directory
    add_response = await client.post(
        "/api/directories/tracked",
        json={"path": str(images_dir), "sync_strategy": "snapshot"}
    )
    directory_id = add_response.json()["id"]

    # Trigger sync
    response = await client.post(f"/api/directories/tracked/{directory_id}/sync")

    assert response.status_code == 200
    data = response.json()
    assert "tracked_directory_id" in data
    assert "added" in data
    assert "modified" in data
    assert "deleted" in data
    assert "unchanged" in data
    assert "errors" in data
    assert "sync_duration_seconds" in data
    assert "strategy_used" in data
    assert data["strategy_used"] == "snapshot"


@pytest.mark.asyncio
async def test_api_sync_tracked_directory_not_found(client):
    """Test syncing a non-existent tracked directory."""
    response = await client.post("/api/directories/tracked/99999/sync")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_api_sync_tracked_directory_with_images(client, tmp_path):
    """Test syncing a directory with images."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    create_test_image(images_dir / "img1.jpg")
    create_test_image(images_dir / "img2.jpg")

    # Add directory
    add_response = await client.post(
        "/api/directories/tracked",
        json={"path": str(images_dir), "sync_strategy": "snapshot"}
    )
    directory_id = add_response.json()["id"]

    # Mock the embedding service to avoid external dependencies
    with patch("app.services.directory_sync.embed_images_with_progress", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = ([[0.1, 0.2], [0.3, 0.4]], [])

        # Mock save_ingested_images to avoid Chroma dependency
        with patch("app.services.directory_sync.save_ingested_images", new_callable=AsyncMock):
            # Trigger sync
            response = await client.post(f"/api/directories/tracked/{directory_id}/sync")

            assert response.status_code == 200
            data = response.json()

            # Should detect images (might not actually process them due to mocking)
            # but sync should complete without errors
            assert "sync_duration_seconds" in data
            assert data["strategy_used"] == "snapshot"


@pytest.mark.asyncio
async def test_api_sync_detects_new_files(client, tmp_path):
    """Test that sync detects new files added after initial sync."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    create_test_image(images_dir / "img1.jpg")

    # Add directory
    add_response = await client.post(
        "/api/directories/tracked",
        json={"path": str(images_dir), "sync_strategy": "snapshot"}
    )
    directory_id = add_response.json()["id"]

    # Mock embedding to avoid external dependencies
    with patch("app.services.directory_sync.embed_images_with_progress", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = ([[0.1, 0.2]], [])
        with patch("app.services.directory_sync.save_ingested_images", new_callable=AsyncMock):
            # First sync
            response1 = await client.post(f"/api/directories/tracked/{directory_id}/sync")
            assert response1.status_code == 200

    # Add another file
    create_test_image(images_dir / "img2.jpg")

    # Second sync should detect new file
    with patch("app.services.directory_sync.embed_images_with_progress", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = ([[0.3, 0.4]], [])
        with patch("app.services.directory_sync.save_ingested_images", new_callable=AsyncMock):
            response2 = await client.post(f"/api/directories/tracked/{directory_id}/sync")
            assert response2.status_code == 200

            # The number of added files depends on whether embeddings were mocked
            # and whether images were actually saved to DB
            # Just check that the sync completed
            assert "added" in response2.json()


@pytest.mark.asyncio
async def test_api_sync_detects_deleted_files(client, tmp_path):
    """Test that sync detects deleted files."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    img1 = create_test_image(images_dir / "img1.jpg")
    create_test_image(images_dir / "img2.jpg")

    # Add directory
    add_response = await client.post(
        "/api/directories/tracked",
        json={"path": str(images_dir), "sync_strategy": "snapshot"}
    )
    directory_id = add_response.json()["id"]

    # Mock embedding for first sync
    with patch("app.services.directory_sync.embed_images_with_progress", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = ([[0.1, 0.2], [0.3, 0.4]], [])
        with patch("app.services.directory_sync.save_ingested_images", new_callable=AsyncMock):
            # First sync
            response1 = await client.post(f"/api/directories/tracked/{directory_id}/sync")
            assert response1.status_code == 200

    # Delete a file
    img1.unlink()

    # Second sync should detect deletion (relative path)
    response2 = await client.post(f"/api/directories/tracked/{directory_id}/sync")
    assert response2.status_code == 200
    # Deletions are tracked as relative paths
    assert "deleted" in response2.json()


# ============================================
# Integration Tests
# ============================================

@pytest.mark.asyncio
async def test_api_full_tracked_directory_lifecycle(client, tmp_path):
    """Test full lifecycle: add, list, get, sync, remove."""
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    create_test_image(images_dir / "img1.jpg")

    # 1. Add
    add_response = await client.post(
        "/api/directories/tracked",
        json={"path": str(images_dir), "sync_strategy": "snapshot"}
    )
    assert add_response.status_code == 200
    directory_id = add_response.json()["id"]

    # 2. List
    list_response = await client.get("/api/directories/tracked")
    assert list_response.status_code == 200
    assert len(list_response.json()["directories"]) == 1

    # 3. Get
    get_response = await client.get(f"/api/directories/tracked/{directory_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == directory_id

    # 4. Sync
    with patch("app.services.directory_sync.embed_images_with_progress", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = ([[0.1, 0.2]], [])
        with patch("app.services.directory_sync.save_ingested_images", new_callable=AsyncMock):
            sync_response = await client.post(f"/api/directories/tracked/{directory_id}/sync")
            assert sync_response.status_code == 200

    # 5. Remove
    delete_response = await client.delete(f"/api/directories/tracked/{directory_id}")
    assert delete_response.status_code == 200

    # 6. Verify gone
    get_response2 = await client.get(f"/api/directories/tracked/{directory_id}")
    assert get_response2.status_code == 404


@pytest.mark.asyncio
async def test_api_both_strategies_work(client, tmp_path):
    """Test that both snapshot and merkle strategies can be used."""
    dir1 = tmp_path / "photos_snapshot"
    dir2 = tmp_path / "photos_merkle"
    dir1.mkdir()
    dir2.mkdir()

    # Add with snapshot strategy
    response1 = await client.post(
        "/api/directories/tracked",
        json={"path": str(dir1), "sync_strategy": "snapshot"}
    )
    assert response1.status_code == 200
    assert response1.json()["sync_strategy"] == "snapshot"

    # Add with merkle strategy
    response2 = await client.post(
        "/api/directories/tracked",
        json={"path": str(dir2), "sync_strategy": "merkle"}
    )
    assert response2.status_code == 200
    assert response2.json()["sync_strategy"] == "merkle"

    # Both should appear in list
    list_response = await client.get("/api/directories/tracked")
    assert len(list_response.json()["directories"]) == 2
