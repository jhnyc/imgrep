from typing import AsyncGenerator, Optional

from fastapi import Depends

from sqlalchemy.ext.asyncio import AsyncSession

from .core.database import AsyncSessionLocal
from .services.image_service import ImageService
from .services.search_service import SearchService
from .services.ingestion_job import IngestionJobService
from .services.directory_sync import DirectorySyncService
from .services.vector_store import VectorStoreService


# ============================================================================
# Singleton Services (must be defined first)
# ============================================================================

# VectorStoreService is a singleton (ChromaDB requires single client)
_vector_store_service: Optional[VectorStoreService] = None


def get_vector_store_service() -> VectorStoreService:
    """
    Get the VectorStoreService singleton.

    ChromaDB's PersistentClient must be a singleton, so we manage it here.

    Returns:
        VectorStoreService: The vector store service instance
    """
    global _vector_store_service
    if _vector_store_service is None:
        _vector_store_service = VectorStoreService()
    return _vector_store_service


# DirectorySyncService maintains background task state
_directory_sync_service: Optional[DirectorySyncService] = None


def get_directory_sync_service() -> DirectorySyncService:
    """
    Get the DirectorySyncService singleton.

    This service manages background sync tasks and must maintain state
    across requests, so it uses a singleton pattern.

    Returns:
        DirectorySyncService: The directory sync service instance
    """
    global _directory_sync_service
    if _directory_sync_service is None:
        # Initialize with vector_store service
        vector_store = get_vector_store_service()
        _directory_sync_service = DirectorySyncService(
            vector_store=vector_store,
        )
    return _directory_sync_service


# ============================================================================
# Core Dependencies
# ============================================================================

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session.

    Yields:
        AsyncSession: A database session
    """
    async with AsyncSessionLocal() as session:
        yield session


# ============================================================================
# Service Dependencies
# ============================================================================

async def get_image_service(
    session: AsyncSession = Depends(get_db_session)
) -> AsyncGenerator[ImageService, None]:
    """
    Get an ImageService instance.

    Args:
        session: Database session

    Yields:
        ImageService: An image service instance
    """
    yield ImageService(session)


async def get_search_service(
    session: AsyncSession = Depends(get_db_session),
    vector_store: VectorStoreService = Depends(get_vector_store_service)
) -> AsyncGenerator[SearchService, None]:
    """
    Get a SearchService instance.

    Args:
        session: Database session
        vector_store: VectorStoreService singleton

    Yields:
        SearchService: A search service instance
    """
    yield SearchService(session, vector_store)


async def get_ingestion_job_service(
    vector_store: VectorStoreService = Depends(get_vector_store_service)
) -> AsyncGenerator[IngestionJobService, None]:
    """
    Get an IngestionJobService instance.

    Args:
        vector_store: VectorStoreService singleton

    Yields:
        IngestionJobService: An ingestion job service instance
    """
    yield IngestionJobService(vector_store=vector_store)


# ============================================================================
# Factory Functions (for background tasks that can't use Depends)
# ============================================================================

def create_image_service(session: AsyncSession) -> ImageService:
    """Create an ImageService instance for background tasks."""
    return ImageService(session)


def create_search_service(session: AsyncSession, vector_store: VectorStoreService) -> SearchService:
    """Create a SearchService instance for background tasks."""
    return SearchService(session, vector_store)


def create_ingestion_job_service(vector_store: VectorStoreService) -> IngestionJobService:
    """Create an IngestionJobService instance for background tasks."""
    return IngestionJobService(vector_store=vector_store)
