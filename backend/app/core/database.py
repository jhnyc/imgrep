import json
from pathlib import Path
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from ..models.sql import Base, Image, Embedding, ClusteringRun, ClusterAssignment, ClusterMetadata
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


# Helper functions
async def get_image_by_hash(file_hash: str) -> Optional[Image]:
    """Get image by file hash"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Image).where(Image.file_hash == file_hash)
        )
        return result.scalar_one_or_none()


async def get_all_image_ids() -> List[int]:
    """Get all image IDs for corpus hash computation"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Image.id).order_by(Image.id))
        return [row[0] for row in result.all()]


async def get_all_embeddings() -> Dict[int, List[float]]:
    """Get all image embeddings as {image_id: embedding_vector}"""
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


async def get_current_clustering_run(strategy: str, projection_strategy: str, overlap_strategy: str, corpus_hash: str) -> Optional[ClusteringRun]:
    """Get current clustering run for strategy, projection and overlap if corpus matches"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ClusteringRun)
            .where(
                ClusteringRun.strategy == strategy,
                ClusteringRun.projection_strategy == projection_strategy,
                ClusteringRun.overlap_strategy == overlap_strategy,
                ClusteringRun.image_corpus_hash == corpus_hash,
                ClusteringRun.is_current == True
            )
        )
        return result.scalar_one_or_none()


async def get_all_clustering_runs_for_corpus(corpus_hash: str) -> List[ClusteringRun]:
    """Get all clustering runs for a specific corpus hash"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ClusteringRun)
            .where(ClusteringRun.image_corpus_hash == corpus_hash)
        )
        return list(result.scalars().all())


async def set_current_clustering_run(run_id: int, strategy: str, projection_strategy: str, overlap_strategy: str):
    """Set a clustering run as current, unsetting others for same strategy/projection/overlap"""
    async with AsyncSessionLocal() as session:
        # Unset previous current runs for the same strategy, projection and overlap
        from sqlalchemy import update
        await session.execute(
            update(ClusteringRun)
            .where(
                ClusteringRun.strategy == strategy,
                ClusteringRun.projection_strategy == projection_strategy,
                ClusteringRun.overlap_strategy == overlap_strategy
            )
            .values(is_current=False)
        )
        await session.execute(
            update(ClusteringRun)
            .where(ClusteringRun.id == run_id)
            .values(is_current=True)
        )
        await session.commit()
