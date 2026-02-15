import warnings
import os
import shutil
from pathlib import Path
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
import asyncio
from contextlib import asynccontextmanager

# Set database name environment variable before importing app logic
os.environ["DB_NAME"] = "test_app.db"

# Import app components after setting env var
from app.main import app
from app.core.database import init_db, engine, AsyncSessionLocal
from app.core.config import DB_PATH
from app.services.vector_store import VectorStoreService

# Suppress DeprecationWarnings from external libraries during tests
warnings.filterwarnings("ignore", category=DeprecationWarning)

@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture
async def test_db():
    """Database setup fixture - initializes schema and handles cleanup.

    Use this when you just need the database ready but will create
    your own sessions using AsyncSessionLocal().
    """
    # Ensure clean slate
    if DB_PATH.exists():
        os.remove(DB_PATH)

    # Initialize DB schema
    await init_db()

    yield

    # Cleanup
    await engine.dispose()
    if DB_PATH.exists():
        os.remove(DB_PATH)


@pytest_asyncio.fixture
async def db_session(test_db):
    """Provides an async database session for tests.

    Usage:
        async with db_session() as session:
            # use session here
    """
    @asynccontextmanager
    async def _get_session():
        async with AsyncSessionLocal() as session:
            yield session

    return _get_session


@pytest_asyncio.fixture
async def client(test_db):
    """Async client for testing."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def chroma_test_manager():
    """Create a temporary Chroma instance for testing.

    This fixture also sets up the app's dependency override so that
    the test Chroma instance is used instead of the real one.
    """
    from app.core.config import CHROMA_DATA_PATH

    test_path = CHROMA_DATA_PATH.parent / "chroma_test"
    if test_path.exists():
        shutil.rmtree(test_path)

    manager = VectorStoreService()
    test_collection_name = "test_images"

    # Clean up if collection exists
    try:
        manager.client.delete_collection(test_collection_name)
    except:
        pass

    collection = manager.client.get_or_create_collection(
        name=test_collection_name,
        metadata={"hnsw:space": "cosine"}
    )
    manager.collection = collection

    # Override the dependency for the app
    from app.dependencies import get_vector_store_service
    original = get_vector_store_service

    def _override():
        return manager

    app.dependency_overrides[get_vector_store_service] = _override

    yield manager

    # Clean up
    try:
        manager.client.delete_collection(test_collection_name)
    except:
        pass

    # Remove the override
    app.dependency_overrides.clear()
