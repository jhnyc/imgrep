"""
Database layer with libSQL support for native vector search.

Uses sync SQLAlchemy with libSQL dialect, wrapped for async FastAPI compatibility.
"""
import asyncio
import struct
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import partial
from typing import Optional, List, Dict, Tuple

from sqlalchemy import create_engine, select, update, func, text
from sqlalchemy.orm import sessionmaker, Session

from .models import Base, Image, Embedding, ClusteringRun, ClusterAssignment, ClusterMetadata
from .constants import DATABASE_URL, EMBEDDING_DIM

# Thread pool for running sync DB operations in async context
_executor = ThreadPoolExecutor(max_workers=4)

# Sync engine for libSQL
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


@contextmanager
def get_session():
    """Get a database session (sync context manager)"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


async def run_in_executor(func, *args, **kwargs):
    """Run a sync function in thread pool for async compatibility"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, partial(func, *args, **kwargs))


# Alias for backwards compatibility with existing code
# This wraps sync session methods in async executors
class AsyncSessionWrapper:
    """
    Async wrapper around a sync SQLAlchemy Session.
    
    Allows using `await session.execute(...)`, `await session.commit()`, etc.
    by running sync operations in a thread pool executor.
    """
    
    def __init__(self, session: Session):
        self._session = session
    
    async def execute(self, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor, partial(self._session.execute, *args, **kwargs)
        )
    
    async def flush(self, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor, partial(self._session.flush, *args, **kwargs)
        )
    
    async def commit(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._session.commit)
    
    async def refresh(self, instance, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor, partial(self._session.refresh, instance, *args, **kwargs)
        )
    
    async def rollback(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._session.rollback)
    
    def add(self, instance, _warn=True):
        """Sync add - doesn't need await"""
        return self._session.add(instance, _warn)
    
    def add_all(self, instances):
        """Sync add_all - doesn't need await"""
        return self._session.add_all(instances)
    
    def delete(self, instance):
        """Sync delete - doesn't need await"""
        return self._session.delete(instance)
    
    def close(self):
        """Sync close - doesn't need await"""
        return self._session.close()


class AsyncSessionLocal:
    """Async-compatible session factory for libSQL sync sessions"""
    
    def __init__(self):
        self._session: Optional[Session] = None
        self._wrapper: Optional[AsyncSessionWrapper] = None
    
    async def __aenter__(self) -> AsyncSessionWrapper:
        self._session = SessionLocal()
        self._wrapper = AsyncSessionWrapper(self._session)
        return self._wrapper
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            self._session.close()
            self._session = None
            self._wrapper = None


# ============================================================================
# Vector Utilities
# ============================================================================

def float_list_to_f32_blob(floats: List[float]) -> bytes:
    """Convert a list of floats to F32_BLOB format for libSQL vector storage."""
    return struct.pack(f'{len(floats)}f', *floats)


def f32_blob_to_float_list(blob: bytes) -> List[float]:
    """Convert F32_BLOB back to a list of floats."""
    count = len(blob) // 4  # 4 bytes per float32
    return list(struct.unpack(f'{count}f', blob))


# ============================================================================
# Database Initialization
# ============================================================================

def _init_db_sync():
    """Initialize database tables (sync)"""
    Base.metadata.create_all(bind=engine)


async def init_db():
    """Initialize database tables"""
    await run_in_executor(_init_db_sync)


# ============================================================================
# Helper Functions (now async wrappers around sync operations)
# ============================================================================

def _get_image_by_hash_sync(file_hash: str) -> Optional[Image]:
    with get_session() as session:
        result = session.execute(
            select(Image).where(Image.file_hash == file_hash)
        )
        return result.scalar_one_or_none()


async def get_image_by_hash(file_hash: str) -> Optional[Image]:
    """Get image by file hash"""
    return await run_in_executor(_get_image_by_hash_sync, file_hash)


def _get_all_image_ids_sync() -> List[int]:
    with get_session() as session:
        result = session.execute(select(Image.id).order_by(Image.id))
        return [row[0] for row in result.all()]


async def get_all_image_ids() -> List[int]:
    """Get all image IDs for corpus hash computation"""
    return await run_in_executor(_get_all_image_ids_sync)


def _get_all_embeddings_sync() -> Dict[int, List[float]]:
    with get_session() as session:
        result = session.execute(
            select(Image.id, Embedding.vector)
            .join(Embedding)
            .where(Image.embedding_id.isnot(None))
        )
        return {
            row[0]: f32_blob_to_float_list(row[1])
            for row in result.all()
        }


async def get_all_embeddings() -> Dict[int, List[float]]:
    """Get all image embeddings as {image_id: embedding_vector}"""
    return await run_in_executor(_get_all_embeddings_sync)


def _get_current_clustering_run_sync(strategy: str, corpus_hash: str) -> Optional[ClusteringRun]:
    with get_session() as session:
        result = session.execute(
            select(ClusteringRun)
            .where(
                ClusteringRun.strategy == strategy,
                ClusteringRun.image_corpus_hash == corpus_hash,
                ClusteringRun.is_current == True
            )
        )
        return result.scalar_one_or_none()


async def get_current_clustering_run(strategy: str, corpus_hash: str) -> Optional[ClusteringRun]:
    """Get current clustering run for strategy if corpus matches"""
    return await run_in_executor(_get_current_clustering_run_sync, strategy, corpus_hash)


def _set_current_clustering_run_sync(run_id: int, strategy: str):
    with get_session() as session:
        session.execute(
            update(ClusteringRun)
            .where(ClusteringRun.strategy == strategy)
            .values(is_current=False)
        )
        session.execute(
            update(ClusteringRun)
            .where(ClusteringRun.id == run_id)
            .values(is_current=True)
        )
        session.commit()


async def set_current_clustering_run(run_id: int, strategy: str):
    """Set a clustering run as current, unsetting others for same strategy"""
    await run_in_executor(_set_current_clustering_run_sync, run_id, strategy)


# ============================================================================
# Vector Similarity Search
# ============================================================================

def _search_similar_embeddings_sync(
    query_vector: List[float],
    top_k: int = 20
) -> List[Tuple[int, float]]:
    """
    Search for similar embeddings using libSQL native vector_distance_cos.
    
    Returns: List of (image_id, similarity_score) tuples, ordered by similarity descending.
    Note: vector_distance_cos returns cosine DISTANCE (0=identical, 1=orthogonal, 2=opposite)
          We convert to similarity (1 - distance/2) for backwards compatibility.
    """
    query_blob = float_list_to_f32_blob(query_vector)
    
    with get_session() as session:
        # Use raw SQL for vector search since SQLAlchemy doesn't know about vector functions
        # COALESCE handles NULL distances (from zero vectors) by assigning max distance
        result = session.execute(
            text("""
                SELECT 
                    images.id,
                    vector_distance_cos(embeddings.vector, :query_vector) as distance
                FROM images
                JOIN embeddings ON images.embedding_id = embeddings.id
                WHERE images.embedding_status = 'completed'
                  AND vector_distance_cos(embeddings.vector, :query_vector) IS NOT NULL
                ORDER BY distance ASC
                LIMIT :limit
            """),
            {"query_vector": query_blob, "limit": top_k}
        )
        
        rows = result.fetchall()
        # Convert distance to similarity: similarity = 1 - (distance / 2)
        # distance=0 -> similarity=1, distance=1 -> similarity=0.5, distance=2 -> similarity=0
        return [(row[0], 1.0 - (row[1] / 2.0)) for row in rows]


async def search_similar_embeddings(
    query_vector: List[float],
    top_k: int = 20
) -> List[Tuple[int, float]]:
    """
    Search for similar embeddings using native vector similarity.
    
    Args:
        query_vector: Query embedding vector (list of floats)
        top_k: Number of results to return
        
    Returns:
        List of (image_id, similarity_score) tuples, ordered by similarity descending.
    """
    return await run_in_executor(_search_similar_embeddings_sync, query_vector, top_k)


# ============================================================================
# Embedding Queue Functions
# ============================================================================

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def is_retryable_error(status_code: int) -> bool:
    """Check if an HTTP status code is retryable"""
    return status_code in RETRYABLE_STATUS_CODES


def calculate_next_retry_at(retry_count: int) -> datetime:
    """Calculate next retry time using exponential backoff"""
    from .constants import RETRY_BASE_DELAY_SECONDS
    delay_seconds = RETRY_BASE_DELAY_SECONDS * (2 ** retry_count)
    return datetime.utcnow() + timedelta(seconds=delay_seconds)


def _create_image_with_pending_status_sync(
    file_hash: str,
    file_path: str,
    thumbnail_path: Optional[str],
    width: Optional[int],
    height: Optional[int],
) -> Image:
    with get_session() as session:
        image = Image(
            file_hash=file_hash,
            file_path=file_path,
            thumbnail_path=thumbnail_path,
            width=width,
            height=height,
            embedding_status="pending",
            retry_count=0,
        )
        session.add(image)
        session.commit()
        session.refresh(image)
        return image


async def create_image_with_pending_status(
    file_hash: str,
    file_path: str,
    thumbnail_path: Optional[str],
    width: Optional[int],
    height: Optional[int],
) -> Image:
    """Create a new image record with pending embedding status"""
    return await run_in_executor(
        _create_image_with_pending_status_sync,
        file_hash, file_path, thumbnail_path, width, height
    )


def _mark_embedding_processing_sync(image_id: int):
    with get_session() as session:
        session.execute(
            update(Image)
            .where(Image.id == image_id)
            .values(embedding_status="processing")
        )
        session.commit()


async def mark_embedding_processing(image_id: int):
    """Mark an image as currently being processed"""
    await run_in_executor(_mark_embedding_processing_sync, image_id)


def _mark_embedding_complete_sync(image_id: int, embedding_id: int):
    with get_session() as session:
        session.execute(
            update(Image)
            .where(Image.id == image_id)
            .values(
                embedding_status="completed",
                embedding_id=embedding_id,
                error_code=None,
                error_message=None,
            )
        )
        session.commit()


async def mark_embedding_complete(image_id: int, embedding_id: int):
    """Mark an image as successfully embedded"""
    await run_in_executor(_mark_embedding_complete_sync, image_id, embedding_id)


def _mark_embedding_failed_permanent_sync(image_id: int, error_code: str, error_message: str):
    with get_session() as session:
        session.execute(
            update(Image)
            .where(Image.id == image_id)
            .values(
                embedding_status="failed_permanent",
                error_code=error_code,
                error_message=error_message,
            )
        )
        session.commit()


async def mark_embedding_failed_permanent(image_id: int, error_code: str, error_message: str):
    """Mark an image as permanently failed (non-retryable error)"""
    await run_in_executor(_mark_embedding_failed_permanent_sync, image_id, error_code, error_message)


def _mark_for_retry_sync(image_id: int, error_code: str, error_message: str):
    from .constants import MAX_RETRY_COUNT
    
    with get_session() as session:
        result = session.execute(
            select(Image.retry_count).where(Image.id == image_id)
        )
        current_retry_count = result.scalar_one_or_none() or 0
        new_retry_count = current_retry_count + 1
        
        if new_retry_count >= MAX_RETRY_COUNT:
            session.execute(
                update(Image)
                .where(Image.id == image_id)
                .values(
                    embedding_status="failed_permanent",
                    error_code=error_code,
                    error_message=f"Max retries ({MAX_RETRY_COUNT}) exceeded. Last error: {error_message}",
                    retry_count=new_retry_count,
                )
            )
        else:
            next_retry = calculate_next_retry_at(new_retry_count)
            session.execute(
                update(Image)
                .where(Image.id == image_id)
                .values(
                    embedding_status="failed_retryable",
                    error_code=error_code,
                    error_message=error_message,
                    retry_count=new_retry_count,
                    next_retry_at=next_retry,
                )
            )
        session.commit()


async def mark_for_retry(image_id: int, error_code: str, error_message: str):
    """Mark an image for retry with exponential backoff"""
    await run_in_executor(_mark_for_retry_sync, image_id, error_code, error_message)


def _get_pending_retries_sync(limit: int) -> List[Image]:
    with get_session() as session:
        now = datetime.utcnow()
        result = session.execute(
            select(Image)
            .where(
                Image.embedding_status == "failed_retryable",
                Image.next_retry_at <= now,
            )
            .order_by(Image.next_retry_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def get_pending_retries(limit: int) -> List[Image]:
    """Get images that are ready for retry."""
    return await run_in_executor(_get_pending_retries_sync, limit)


def _get_queue_stats_sync() -> Dict[str, int]:
    with get_session() as session:
        result = session.execute(
            select(Image.embedding_status, func.count(Image.id))
            .group_by(Image.embedding_status)
        )
        status_counts = {row[0]: row[1] for row in result.all()}
        
        total = sum(status_counts.values())
        
        return {
            "total": total,
            "pending": status_counts.get("pending", 0),
            "processing": status_counts.get("processing", 0),
            "completed": status_counts.get("completed", 0),
            "failed_retryable": status_counts.get("failed_retryable", 0),
            "failed_permanent": status_counts.get("failed_permanent", 0),
        }


async def get_queue_stats() -> Dict[str, int]:
    """Get statistics about the embedding queue"""
    return await run_in_executor(_get_queue_stats_sync)
