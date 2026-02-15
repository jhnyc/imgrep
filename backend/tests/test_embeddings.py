"""Tests for embedding service."""
import base64
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.embedding import (
    EmbeddingProgress,
    embed_images_with_progress,
    get_embedding_info,
)


@pytest.mark.asyncio
async def test_embed_text_async():
    """Test text embedding using SigLIP"""
    # This test will actually use the SigLIP model
    # For unit testing, we mock the embedder
    with patch("app.services.embeddings.siglip.get_siglip_embedder") as mock_get_embedder:
        mock_embedder = MagicMock()
        mock_embedder.embed_text.return_value = [0.1, 0.2, 0.3, 0.4]
        mock_get_embedder.return_value = mock_embedder

        from app.services.embedding import embed_text_async
        result = await embed_text_async("test query")

        assert result == [0.1, 0.2, 0.3, 0.4]
        mock_embedder.embed_text.assert_called_once_with("test query")


def test_embedding_progress():
    """Test EmbeddingProgress tracker."""
    progress = EmbeddingProgress(total=10)

    assert progress.total == 10
    assert progress.processed == 0
    assert progress.progress == 0.0
    assert progress.errors == []

    progress.update(5)
    assert progress.processed == 5
    assert progress.progress == 0.5

    progress.add_error("Test error")
    assert len(progress.errors) == 1

    progress.update(5)
    assert progress.progress == 1.0

    result = progress.to_dict()
    assert result["total"] == 10
    assert result["processed"] == 10
    assert result["progress"] == 1.0
    assert "Test error" in result["errors"]


def test_embedding_progress_zero_total():
    """Test EmbeddingProgress with zero total."""
    progress = EmbeddingProgress(total=0)
    assert progress.progress == 1.0


@pytest.mark.asyncio
async def test_embed_images_with_progress_success(tmp_path):
    """Test batch image embedding with progress tracking."""
    # Create fake image files
    img1 = tmp_path / "img1.jpg"
    img2 = tmp_path / "img2.jpg"
    img1.write_bytes(b"fake1")
    img2.write_bytes(b"fake2")

    mock_embeddings = [[0.1, 0.2], [0.3, 0.4]]
    progress_updates = []

    async def progress_callback(data):
        progress_updates.append(data)

    with patch("app.services.embeddings.siglip.get_siglip_embedder") as mock_get_embedder:
        mock_embedder = MagicMock()
        mock_embedder.embed_images_batch.return_value = mock_embeddings
        mock_get_embedder.return_value = mock_embedder

        result, errors = await embed_images_with_progress(
            [img1, img2],
            batch_size=2,
            progress_callback=progress_callback
        )

        assert len(result) == 2
        assert result == mock_embeddings
        assert len(errors) == 0
        assert len(progress_updates) == 1
        assert progress_updates[0]["progress"] == 1.0


@pytest.mark.asyncio
async def test_embed_images_with_progress_batch_error(tmp_path):
    """Test batch embedding with one failed batch."""
    img1 = tmp_path / "img1.jpg"
    img2 = tmp_path / "img2.jpg"
    img3 = tmp_path / "img3.jpg"
    img4 = tmp_path / "img4.jpg"
    for img in [img1, img2, img3, img4]:
        img.write_bytes(b"fake")

    async def progress_callback(data):
        pass

    call_count = 0

    def mock_embed_batch(images):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return [[0.1, 0.2]]
        raise Exception("Model error")

    with patch("app.services.embeddings.siglip.get_siglip_embedder") as mock_get_embedder:
        mock_embedder = MagicMock()
        mock_embedder.embed_images_batch.side_effect = mock_embed_batch
        mock_get_embedder.return_value = mock_embedder

        result, errors = await embed_images_with_progress(
            [img1, img2, img3, img4],
            batch_size=2,
            progress_callback=progress_callback
        )

        assert len(result) == 1
        assert len(errors) == 1
        assert "Model error" in errors[0]


@pytest.mark.asyncio
async def test_get_embedding_info():
    """Test getting embedding backend info"""
    with patch("app.services.embeddings.siglip.get_siglip_embedder") as mock_get_embedder:
        mock_embedder = MagicMock()
        mock_embedder.model_name = "google/siglip-base-patch16-512"
        mock_embedder.embedding_dim = 768
        mock_get_embedder.return_value = mock_embedder

        info = await get_embedding_info()

        assert info["backend"] == "siglip"
        assert info["model"] == "google/siglip-base-patch16-512"
        assert info["embedding_dim"] == 768
        assert info["type"] == "local"
