"""Tests for embedding service."""
import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import HTTPStatusError, Response

from app.embeddings import (
    EmbeddingProgress,
    embed_text_async,
    embed_image_bytes_async,
    embed_images_batch_async,
    embed_images_with_progress,
)


@pytest.mark.asyncio
async def test_embed_text_async_success():
    """Test successful text embedding."""
    mock_response = {
        "data": [{"embedding": [0.1, 0.2, 0.3, 0.4]}]
    }

    with patch("app.embeddings.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response_obj
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = await embed_text_async("test query")

        assert result == [0.1, 0.2, 0.3, 0.4]
        mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_embed_text_async_http_error():
    """Test text embedding with HTTP error."""
    with patch("app.embeddings.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=mock_response
        )
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client_class.return_value = mock_client

        with pytest.raises(HTTPStatusError):
            await embed_text_async("test query")


@pytest.mark.asyncio
async def test_embed_image_bytes_async():
    """Test embedding image bytes."""
    mock_response = {
        "data": [{"embedding": [0.5, 0.6, 0.7, 0.8]}]
    }

    with patch("app.embeddings.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response_obj
        mock_client.__aenter__.return_value = mock_client
        mock_client_class.return_value = mock_client

        result = await embed_image_bytes_async(b"fake image bytes")

        assert result == [0.5, 0.6, 0.7, 0.8]

        # Verify the image was base64 encoded
        call_args = mock_client.post.call_args
        assert "image" in call_args[1]["json"]["input"][0]


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

    with patch("app.embeddings._embed_single_batch", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = mock_embeddings

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

    async def mock_embed_batch(client, paths):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return [[0.1, 0.2]]
        raise Exception("API error")

    with patch("app.embeddings._embed_single_batch", side_effect=mock_embed_batch):
        result, errors = await embed_images_with_progress(
            [img1, img2, img3, img4],
            batch_size=2,
            progress_callback=progress_callback
        )

        assert len(result) == 1
        assert len(errors) == 1
        assert "API error" in errors[0]


@pytest.mark.asyncio
async def test_embed_images_batch_async(tmp_path):
    """Test basic batch image embedding."""
    img1 = tmp_path / "img1.jpg"
    img2 = tmp_path / "img2.jpg"
    img1.write_bytes(b"fake1")
    img2.write_bytes(b"fake2")

    mock_embeddings = [[0.1, 0.2], [0.3, 0.4]]

    with patch("app.embeddings._embed_single_batch", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = mock_embeddings

        result = await embed_images_batch_async([img1, img2], batch_size=2)

        assert len(result) == 2
        assert result == mock_embeddings
        mock_embed.assert_called_once()
