"""Tests for duplicate image prevention."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database import AsyncSessionLocal
from app.models import Image, Embedding
from app.embeddings import embed_images_batch_async


@pytest.mark.asyncio
async def test_image_unique_constraint(test_db):
    """Test that database enforces unique file_hash."""
    async with AsyncSessionLocal() as session:
        embedding = Embedding(vector="[0.1, 0.2]", model_name="test-model")
        session.add(embedding)
        await session.flush()

        # Add first image
        image1 = Image(
            file_hash="abc123",
            file_path="/path/to/image1.jpg",
            embedding_id=embedding.id
        )
        session.add(image1)
        await session.commit()

    # Try to add duplicate with same hash
    async with AsyncSessionLocal() as session:
        embedding2 = Embedding(vector="[0.3, 0.4]", model_name="test-model")
        session.add(embedding2)
        await session.flush()

        image2 = Image(
            file_hash="abc123",  # Same hash
            file_path="/path/to/image2.jpg",
            embedding_id=embedding2.id
        )
        session.add(image2)

        with pytest.raises(Exception):  # IntegrityError
            await session.commit()


@pytest.mark.asyncio
async def test_get_image_by_hash_finds_existing(test_db):
    """Test get_image_by_hash returns existing image."""
    from app.database import get_image_by_hash, AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        embedding = Embedding(vector="[0.1, 0.2]", model_name="test-model")
        session.add(embedding)
        await session.flush()

        image = Image(
            file_hash="existing_hash",
            file_path="/path/to/image.jpg",
            embedding_id=embedding.id
        )
        session.add(image)
        await session.commit()

    result = await get_image_by_hash("existing_hash")

    assert result is not None
    assert result.file_hash == "existing_hash"


@pytest.mark.asyncio
async def test_get_image_by_hash_returns_none_for_new(test_db):
    """Test get_image_by_hash returns None for new image."""
    from app.database import get_image_by_hash

    result = await get_image_by_hash("new_hash")

    assert result is None


@pytest.mark.asyncio
async def test_process_directory_skips_duplicates(test_db, tmp_path):
    """Test that directory processing skips already embedded images."""
    from app.image_processor import compute_file_hash
    from app.database import get_image_by_hash, AsyncSessionLocal

    # Create test images
    img1 = tmp_path / "image1.jpg"
    img2 = tmp_path / "image2.jpg"
    img1.write_bytes(b"fake_image_1")
    img2.write_bytes(b"fake_image_2")

    hash1 = compute_file_hash(img1)
    hash2 = compute_file_hash(img2)

    # Pre-add one image to database
    async with AsyncSessionLocal() as session:
        embedding = Embedding(vector="[0.1, 0.2]", model_name="test-model")
        session.add(embedding)
        await session.flush()

        existing_image = Image(
            file_hash=hash1,
            file_path=str(img1),
            embedding_id=embedding.id
        )
        session.add(existing_image)
        await session.commit()

    # Simulate duplicate filtering logic
    image_paths = [img1, img2]
    new_images = []

    for img_path in image_paths:
        file_hash = compute_file_hash(img_path)
        existing = await get_image_by_hash(file_hash)
        if existing is None:
            new_images.append(img_path)

    # Should only contain img2 (img1 was duplicate)
    assert len(new_images) == 1
    assert new_images[0] == img2


@pytest.mark.asyncio
async def test_batch_embed_only_new_images(test_db, tmp_path):
    """Test that batch embedding is only called for new images."""
    from app.image_processor import compute_file_hash
    from app.database import get_image_by_hash, AsyncSessionLocal

    # Create test images
    img1 = tmp_path / "image1.jpg"
    img2 = tmp_path / "image2.jpg"
    img1.write_bytes(b"fake_image_1")
    img2.write_bytes(b"fake_image_2")

    hash1 = compute_file_hash(img1)
    hash2 = compute_file_hash(img2)

    # Pre-add img1 to database
    async with AsyncSessionLocal() as session:
        embedding = Embedding(vector="[0.1, 0.2]", model_name="test-model")
        session.add(embedding)
        await session.flush()

        existing_image = Image(
            file_hash=hash1,
            file_path=str(img1),
            embedding_id=embedding.id
        )
        session.add(existing_image)
        await session.commit()

    # Filter out duplicates
    all_images = [img1, img2]
    images_to_embed = []

    for img in all_images:
        h = compute_file_hash(img)
        if await get_image_by_hash(h) is None:
            images_to_embed.append(img)

    # Verify only new image will be embedded
    assert len(images_to_embed) == 1
    assert images_to_embed[0] == img2

    # Mock the embedding call and verify it's called once
    with patch("app.embeddings._embed_single_batch", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [[0.1, 0.2]]

        result = await embed_images_batch_async(images_to_embed, batch_size=2)

        assert len(result) == 1
        mock_embed.assert_called_once()


@pytest.mark.asyncio
async def test_all_duplicates_skipped(test_db, tmp_path):
    """Test when all images are duplicates."""
    from app.image_processor import compute_file_hash
    from app.database import get_image_by_hash, AsyncSessionLocal

    # Create test images
    img1 = tmp_path / "image1.jpg"
    img2 = tmp_path / "image2.jpg"
    img1.write_bytes(b"fake_image_1")
    img2.write_bytes(b"fake_image_2")

    # Add both to database
    async with AsyncSessionLocal() as session:
        for img in [img1, img2]:
            h = compute_file_hash(img)
            embedding = Embedding(vector="[0.1, 0.2]", model_name="test-model")
            session.add(embedding)
            await session.flush()

            image = Image(
                file_hash=h,
                file_path=str(img),
                embedding_id=embedding.id
            )
            session.add(image)
        await session.commit()

    # Filter - should result in empty list
    all_images = [img1, img2]
    new_images = []

    for img in all_images:
        h = compute_file_hash(img)
        if await get_image_by_hash(h) is None:
            new_images.append(img)

    assert len(new_images) == 0


@pytest.mark.asyncio
async def test_different_content_different_hash(tmp_path):
    """Test that different images produce different hashes."""
    from app.image_processor import compute_file_hash

    img1 = tmp_path / "image1.jpg"
    img2 = tmp_path / "image2.jpg"
    img1.write_bytes(b"content_1")
    img2.write_bytes(b"content_2")

    hash1 = compute_file_hash(img1)
    hash2 = compute_file_hash(img2)

    assert hash1 != hash2
    assert len(hash1) == 64  # SHA256 hex length


@pytest.mark.asyncio
async def test_same_content_same_hash(tmp_path):
    """Test that identical content produces same hash."""
    from app.image_processor import compute_file_hash

    img1 = tmp_path / "image1.jpg"
    img2 = tmp_path / "image2.jpg"
    img1.write_bytes(b"same_content")
    img2.write_bytes(b"same_content")

    hash1 = compute_file_hash(img1)
    hash2 = compute_file_hash(img2)

    assert hash1 == hash2
