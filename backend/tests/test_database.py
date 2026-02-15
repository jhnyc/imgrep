"""Tests for database operations."""
import json
import pytest

from app.models.sql import Image, Embedding, ClusteringRun, ClusterAssignment, ClusterMetadata
from app.core.database import (
    get_image_by_hash,
    get_all_image_ids,
    get_all_embeddings,
    get_current_clustering_run,
    set_current_clustering_run,
)


@pytest.mark.asyncio
async def test_get_image_by_hash_not_found(test_db):
    """Test getting non-existent image returns None."""
    result = await get_image_by_hash("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_get_image_by_hash_success(test_db):
    """Test getting image by hash."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        embedding = Embedding(vector="[0.1, 0.2]", model_name="test-model")
        session.add(embedding)
        await session.flush()

        image = Image(
            file_hash="abc123",
            file_path="/path/to/image.jpg",
            embedding_id=embedding.id
        )
        session.add(image)
        await session.commit()

    result = await get_image_by_hash("abc123")

    assert result is not None
    assert result.file_hash == "abc123"
    assert result.file_path == "/path/to/image.jpg"


@pytest.mark.asyncio
async def test_get_all_image_ids_empty(test_db):
    """Test getting image IDs from empty database."""
    result = await get_all_image_ids()
    assert result == []


@pytest.mark.asyncio
async def test_get_all_image_ids(test_db):
    """Test getting all image IDs."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        for i in range(3):
            image = Image(
                file_hash=f"hash{i}",
                file_path=f"/path/{i}.jpg"
            )
            session.add(image)
        await session.commit()

    result = await get_all_image_ids()

    assert len(result) == 3
    assert result == [1, 2, 3]  # Auto-incrementing IDs


@pytest.mark.asyncio
async def test_get_all_embeddings(test_db):
    """Test getting all embeddings with image IDs."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        # Create embeddings and images
        for i in range(2):
            embedding = Embedding(
                vector=json.dumps([0.1 * i, 0.2 * i]),
                model_name="test-model"
            )
            session.add(embedding)
            await session.flush()

            image = Image(
                file_hash=f"hash{i}",
                file_path=f"/path/{i}.jpg",
                embedding_id=embedding.id
            )
            session.add(image)
        await session.commit()

    result = await get_all_embeddings()

    assert len(result) == 2
    assert 1 in result
    assert 2 in result
    assert result[1] == [0.0, 0.0]
    assert result[2] == [0.1, 0.2]


@pytest.mark.asyncio
async def test_get_all_embeddings_excludes_null(test_db):
    """Test that images without embeddings are excluded."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        # Image with embedding
        embedding = Embedding(vector="[0.1, 0.2]", model_name="test-model")
        session.add(embedding)
        await session.flush()

        image1 = Image(
            file_hash="hash1",
            file_path="/path/1.jpg",
            embedding_id=embedding.id
        )
        session.add(image1)

        # Image without embedding
        image2 = Image(
            file_hash="hash2",
            file_path="/path/2.jpg"
        )
        session.add(image2)

        await session.commit()

    result = await get_all_embeddings()

    assert len(result) == 1
    assert 1 in result


@pytest.mark.asyncio
async def test_get_current_clustering_run_none(test_db):
    """Test getting current clustering run when none exists."""
    result = await get_current_clustering_run("hdbscan", "corpus123")
    assert result is None


@pytest.mark.asyncio
async def test_get_current_clustering_run_found(test_db):
    """Test getting current clustering run."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        run = ClusteringRun(
            strategy="hdbscan",
            image_corpus_hash="corpus123",
            is_current=True
        )
        session.add(run)
        await session.commit()

    result = await get_current_clustering_run("hdbscan", "corpus123")

    assert result is not None
    assert result.strategy == "hdbscan"
    assert result.image_corpus_hash == "corpus123"
    assert result.is_current is True


@pytest.mark.asyncio
async def test_get_current_clustering_run_wrong_strategy(test_db):
    """Test that current run is strategy-specific."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        run = ClusteringRun(
            strategy="hdbscan",
            image_corpus_hash="corpus123",
            is_current=True
        )
        session.add(run)
        await session.commit()

    result = await get_current_clustering_run("kmeans", "corpus123")
    assert result is None


@pytest.mark.asyncio
async def test_get_current_clustering_run_not_current(test_db):
    """Test that non-current runs are not returned."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        run = ClusteringRun(
            strategy="hdbscan",
            image_corpus_hash="corpus123",
            is_current=False
        )
        session.add(run)
        await session.commit()

    result = await get_current_clustering_run("hdbscan", "corpus123")
    assert result is None


@pytest.mark.asyncio
async def test_set_current_clustering_run(test_db):
    """Test setting a clustering run as current."""
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        # Create two runs for same strategy
        run1 = ClusteringRun(
            strategy="hdbscan",
            image_corpus_hash="corpus123",
            is_current=True
        )
        run2 = ClusteringRun(
            strategy="hdbscan",
            image_corpus_hash="corpus456",
            is_current=False
        )
        session.add_all([run1, run2])
        await session.commit()

    # Set run2 as current
    await set_current_clustering_run(2, "hdbscan")

    # Verify run1 is no longer current
    async with AsyncSessionLocal() as session:
        result1 = await session.execute(
            select(ClusteringRun).where(ClusteringRun.id == 1)
        )
        run1_updated = result1.scalar_one()
        assert run1_updated.is_current is False

        result2 = await session.execute(
            select(ClusteringRun).where(ClusteringRun.id == 2)
        )
        run2_updated = result2.scalar_one()
        assert run2_updated.is_current is True


@pytest.mark.asyncio
async def test_clustering_run_relationships(test_db):
    """Test ClusteringRun relationships with assignments and metadata."""
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    async with AsyncSessionLocal() as session:
        # Create images
        img1 = Image(file_hash="hash1", file_path="/path/1.jpg")
        img2 = Image(file_hash="hash2", file_path="/path/2.jpg")
        session.add_all([img1, img2])
        await session.flush()

        # Create clustering run
        run = ClusteringRun(
            strategy="kmeans",
            image_corpus_hash="corpus123",
            is_current=True
        )
        session.add(run)
        await session.flush()

        # Create assignments
        assign1 = ClusterAssignment(
            clustering_run_id=run.id,
            image_id=img1.id,
            cluster_label=0
        )
        assign2 = ClusterAssignment(
            clustering_run_id=run.id,
            image_id=img2.id,
            cluster_label=1
        )
        session.add_all([assign1, assign2])

        # Create metadata
        meta = ClusterMetadata(
            clustering_run_id=run.id,
            cluster_label=0,
            center_x=100.0,
            center_y=200.0,
            image_count=1
        )
        session.add(meta)

        await session.commit()

        # Query and verify relationships within same session
        result = await session.execute(
            select(ClusteringRun)
            .options(
                selectinload(ClusteringRun.assignments),
                selectinload(ClusteringRun.cluster_metadata_list)
            )
            .where(ClusteringRun.id == run.id)
        )
        retrieved_run = result.scalar_one()

        assert len(retrieved_run.assignments) == 2
        assert len(retrieved_run.cluster_metadata_list) == 1
        assert retrieved_run.cluster_metadata_list[0].center_x == 100.0
