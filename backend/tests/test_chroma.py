import pytest
import numpy as np
import json
from pathlib import Path
from app.services.chroma import ChromaManager
from app.core.config import CHROMA_DATA_PATH
import shutil
import os

@pytest.fixture
def chroma_test_manager():
    """Create a temporary Chroma instance for testing"""
    test_path = CHROMA_DATA_PATH.parent / "chroma_test"
    if test_path.exists():
        shutil.rmtree(test_path)
    
    # We need to monkeypatch or just create a new manager with this path
    manager = ChromaManager()
    # For testing, we'll use a different collection name
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
    
    yield manager
    
    # Cleanup
    try:
        manager.client.delete_collection(test_collection_name)
    except:
        pass

def test_chroma_add_and_search(chroma_test_manager):
    """Test basic add and search functionality"""
    ids = ["1", "2", "3"]
    embeddings = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.9, 0.1, 0.0]  # Close to id 1
    ]
    metadatas = [
        {"file_path": "path/1"},
        {"file_path": "path/2"},
        {"file_path": "path/3"}
    ]
    
    chroma_test_manager.add_embeddings(ids, embeddings, metadatas)
    
    # Search for something close to [1, 0, 0]
    query = [1.0, 0.0, 0.0]
    results = chroma_test_manager.search_by_vector(query, top_k=2)
    
    assert results["ids"][0][0] == "1"
    assert results["ids"][0][1] == "3"
    assert len(results["ids"][0]) == 2
    assert results["metadatas"][0][0]["file_path"] == "path/1"

def test_chroma_delete(chroma_test_manager):
    """Test deleting from Chroma"""
    ids = ["1", "2"]
    embeddings = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    chroma_test_manager.add_embeddings(ids, embeddings)
    
    assert chroma_test_manager.collection.count() == 2
    
    chroma_test_manager.delete_by_ids(["1"])
    assert chroma_test_manager.collection.count() == 1
    
    results = chroma_test_manager.collection.get(ids=["1"])
    assert len(results["ids"]) == 0

@pytest.mark.asyncio
async def test_search_integration(client, test_db, chroma_test_manager, monkeypatch):
    """Test search API integration with Chroma and SQLite"""
    from app.api.search import chroma_manager
    from app.core.database import AsyncSessionLocal
    from app.models.sql import Image, Embedding
    
    # Mock chroma_manager in the search module
    monkeypatch.setattr("app.api.search.chroma_manager", chroma_test_manager)
    
    # 1. Add data to SQLite
    async with AsyncSessionLocal() as session:
        emb1 = Embedding(vector=json.dumps([1.0, 0.0, 0.0]), model_name="test")
        emb2 = Embedding(vector=json.dumps([0.0, 1.0, 0.0]), model_name="test")
        session.add_all([emb1, emb2])
        await session.flush()
        
        img1 = Image(file_hash="h1", file_path="p1", embedding_id=emb1.id, thumbnail_path="t1.jpg")
        img2 = Image(file_hash="h2", file_path="p2", embedding_id=emb2.id, thumbnail_path="t2.jpg")
        session.add_all([img1, img2])
        await session.commit()
        
        img1_id = img1.id
        img2_id = img2.id

    # 2. Add data to Chroma
    chroma_test_manager.add_embeddings(
        ids=[str(img1_id), str(img2_id)],
        embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        metadatas=[{"file_hash": "h1"}, {"file_hash": "h2"}]
    )

    # 3. Mock embedding function to return [1, 0, 0] for our query
    async def mock_embed_text(text: str):
        return [1.0, 0.0, 0.0]
    monkeypatch.setattr("app.api.search.embed_text_async", mock_embed_text)

    # 4. Perform search
    response = await client.post("/api/search/text", json={"query": "test", "top_k": 5})
    
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["results"]) == 2
    assert data["results"][0]["image_id"] == img1_id
    assert data["results"][0]["thumbnail_url"] == "/api/thumbnails/t1.jpg"
    assert data["results"][0]["similarity"] > 0.99
