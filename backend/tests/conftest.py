import warnings
import os
import shutil
from pathlib import Path
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
import asyncio

# Set database name environment variable before importing app logic
os.environ["DB_NAME"] = "test_app.db"

# Import app components after setting env var
from app.main import app
from app.database import init_db, DB_PATH, engine

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
    """Create a fresh database for tests."""
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
async def client(test_db):
    """Async client for testing."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
