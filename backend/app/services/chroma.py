"""
Chroma service - handles vector database operations using ChromaDB.
"""
import chromadb
from chromadb.config import Settings
from pathlib import Path
from typing import List, Optional, Dict, Any
import numpy as np

from ..core.config import CHROMA_DATA_PATH, CHROMA_COLLECTION_NAME


class ChromaManager:
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DATA_PATH),
            settings=Settings(anonymized_telemetry=False)
        )
        # Using cosine similarity as it's common for CLIP embeddings
        self.collection = self.client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )

    def add_embeddings(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None
    ):
        """Add embeddings to the collection"""
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas
        )

    def search_by_vector(
        self,
        query_embedding: List[float],
        top_k: int = 20
    ) -> Dict[str, Any]:
        """Search by embedding vector"""
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["metadatas", "distances"]
        )
        return results

    def delete_by_ids(self, ids: List[str]):
        """Delete items from the collection"""
        self.collection.delete(ids=ids)

    def get_all_embeddings(self) -> Dict[str, List[float]]:
        """Get all embeddings from the collection"""
        results = self.collection.get(include=["embeddings"])
        return {
            id_: emb
            for id_, emb in zip(results["ids"], results["embeddings"])
        }


# Global instance
chroma_manager = ChromaManager()
