"""
Database connection and session management.

This module provides database connectivity and session management.

TODO: Move the helper functions below to appropriate repositories:
- get_image_by_hash -> ImageRepository.get_by_hash (already exists)
- get_all_image_ids -> ImageRepository.get_all_ids (already exists)
- get_all_embeddings -> should be in EmbeddingRepository or ClusteringRunRepository
- get_current_clustering_run -> ClusteringRunRepository.get_current_run (exists)
- get_all_clustering_runs_for_corpus -> ClusteringRunRepository.get_all_for_corpus (exists)
- set_current_clustering_run -> ClusteringRunRepository.set_as_current (exists)
"""
from pathlib import Path
from typing import Optional, List, Dict

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, update

from ..models.sql import Base, Image, Embedding, ClusteringRun
from .config import DATABASE_URL

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Get database session"""
    async with AsyncSessionLocal() as session:
        yield session


# ============================================================================
# Helper functions - TODO: Move to appropriate repositories
# These are kept for backward compatibility during refactoring
# ============================================================================

async def get_image_by_hash(file_hash: str) -> Optional[Image]:
    """
    Get image by file hash.

    TODO: Use ImageRepository.get_by_hash instead
    """
    from ..repositories.image import ImageRepository
    async with AsyncSessionLocal() as session:
        repo = ImageRepository(session)
        return await repo.get_by_hash(file_hash)


async def get_all_image_ids() -> List[int]:
    """
    Get all image IDs for corpus hash computation.

    TODO: Use ImageRepository.get_all_ids instead
    """
    from ..repositories.image import ImageRepository
    async with AsyncSessionLocal() as session:
        repo = ImageRepository(session)
        return await repo.get_all_ids()


async def get_all_embeddings() -> Dict[int, List[float]]:
    """
    Get all image embeddings as {image_id: embedding_vector}.

    TODO: Move to EmbeddingRepository
    """
    import json
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Image.id, Embedding.vector)
            .join(Embedding)
            .where(Image.embedding_id.isnot(None))
        )
        return {
            row[0]: json.loads(row[1])
            for row in result.all()
        }


async def get_current_clustering_run(
    strategy: str,
    projection_strategy: str,
    overlap_strategy: str,
    corpus_hash: str
) -> Optional[ClusteringRun]:
    """
    Get current clustering run for strategy, projection and overlap if corpus matches.

    TODO: Use ClusteringRunRepository.get_current_run instead
    """
    from ..repositories.clustering_run import ClusteringRunRepository
    async with AsyncSessionLocal() as session:
        repo = ClusteringRunRepository(session)
        return await repo.get_current_run(
            strategy, projection_strategy, overlap_strategy, corpus_hash
        )


async def get_all_clustering_runs_for_corpus(corpus_hash: str) -> List[ClusteringRun]:
    """
    Get all clustering runs for a specific corpus hash.

    TODO: Use ClusteringRunRepository.get_all_for_corpus instead
    """
    from ..repositories.clustering_run import ClusteringRunRepository
    async with AsyncSessionLocal() as session:
        repo = ClusteringRunRepository(session)
        return await repo.get_all_for_corpus(corpus_hash)


async def set_current_clustering_run(
    run_id: int,
    strategy: str,
    projection_strategy: str,
    overlap_strategy: str
):
    """
    Set a clustering run as current, unsetting others for same strategy/projection/overlap.

    TODO: Use ClusteringRunRepository.set_as_current instead
    """
    from ..repositories.clustering_run import ClusteringRunRepository
    async with AsyncSessionLocal() as session:
        repo = ClusteringRunRepository(session)
        await repo.set_as_current(run_id, strategy, projection_strategy, overlap_strategy)
        await session.commit()
