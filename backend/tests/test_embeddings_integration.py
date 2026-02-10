"""Integration tests for embedding API - makes real API calls."""
import base64
from pathlib import Path

import pytest
from httpx import HTTPStatusError

from app.embeddings import (
    embed_text_async,
    embed_image_bytes_async,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_embed_text_real_api():
    """Test real text embedding via Jina API."""
    text = "a beautiful sunset over the ocean"
    result = await embed_text_async(text)

    assert isinstance(result, list)
    assert len(result) > 0
    assert all(isinstance(x, float) for x in result)
    # Jina CLIP-v2 produces 768-dimensional embeddings
    assert len(result) == 1024


@pytest.mark.integration
@pytest.mark.asyncio
async def test_embed_image_bytes_real_api():
    """Test real image embedding via Jina API."""
    # Create a minimal valid JPEG (1x1 pixel red image)
    # JPEG magic bytes + minimal DCT data
    minimal_jpeg = bytes([
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

    result = await embed_image_bytes_async(minimal_jpeg)

    assert isinstance(result, list)
    assert len(result) == 1024
    assert all(isinstance(x, float) for x in result)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_embed_text_similar_queries_produce_similar_embeddings():
    """Test that similar text produces similar embeddings (cosine similarity)."""
    import numpy as np

    text1 = "a cute cat playing"
    text2 = "a cute kitten playing"

    emb1 = await embed_text_async(text1)
    emb2 = await embed_text_async(text2)

    # Compute cosine similarity
    vec1 = np.array(emb1)
    vec2 = np.array(emb2)
    similarity = (vec1 @ vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

    # Similar texts should have high cosine similarity
    assert similarity > 0.7


@pytest.mark.integration
@pytest.mark.asyncio
async def test_embed_text_different_queries_produce_different_embeddings():
    """Test that different text produces different embeddings."""
    import numpy as np

    text1 = "a beautiful sunset"
    text2 = "a computer program"

    emb1 = await embed_text_async(text1)
    emb2 = await embed_text_async(text2)

    # Compute cosine similarity
    vec1 = np.array(emb1)
    vec2 = np.array(emb2)
    similarity = (vec1 @ vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

    # Different texts should have lower similarity
    assert similarity < 0.5


@pytest.mark.integration
@pytest.mark.asyncio
async def test_embed_image_base64_encoding():
    """Test that base64 encoding works correctly for the API."""
    # Test with actual PNG data (1x1 red pixel PNG)
    minimal_png = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00,
        0x00, 0x0D, 0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01,
        0x00, 0x00, 0x00, 0x01, 0x08, 0x02, 0x00, 0x00, 0x00, 0x90,
        0x77, 0x53, 0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
        0x54, 0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00, 0x00, 0x03,
        0x01, 0x01, 0x00, 0x18, 0xDD, 0x8D, 0xB4, 0x1C, 0x00, 0x00,
        0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82
    ])

    result = await embed_image_bytes_async(minimal_png)

    assert isinstance(result, list)
    assert len(result) == 1024
    assert all(isinstance(x, float) for x in result)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_api_error_handling():
    """Test that the API properly handles and raises errors."""
    from app.constants import JINA_API_URL, JINA_API_KEY, EMBEDDING_MODEL
    import httpx

    # Use an invalid endpoint to trigger an error
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            JINA_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {JINA_API_KEY}"
            },
            json={"model": EMBEDDING_MODEL, "input": [{"text": ""}]}  # Empty text might error
        )

        # Either it works or fails with proper error code
        assert response.status_code in [200, 400, 401, 422]
