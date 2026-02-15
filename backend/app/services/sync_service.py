import json
from ..core.database import AsyncSessionLocal
from ..models.sql import Image, Embedding
from .chroma import chroma_manager
from sqlalchemy import select
from sqlalchemy.orm import selectinload

async def sync_sqlite_to_chroma():
    """Sync embeddings from SQLite to Chroma if they are missing"""
    async with AsyncSessionLocal() as session:
        # Get count of images in SQLite
        result = await session.execute(select(Image).where(Image.embedding_id.isnot(None)))
        sqlite_images = result.scalars().all()
        
        chroma_count = chroma_manager.collection.count()
        
        if len(sqlite_images) == chroma_count:
            print(f"Chroma is already in sync with SQLite ({chroma_count} items)")
            return

        print(f"Syncing SQLite to Chroma: SQLite={len(sqlite_images)}, Chroma={chroma_count}")
        
        # Get all IDs in Chroma
        # For large collections, this might need batching, but for now we assume it fits in memory
        chroma_ids = set(chroma_manager.collection.get(include=[])["ids"])
        
        to_add_ids = []
        to_add_embeddings = []
        to_add_metadatas = []
        
        for img in sqlite_images:
            if str(img.id) not in chroma_ids:
                # Load embedding
                emb_result = await session.execute(select(Embedding).where(Embedding.id == img.embedding_id))
                embedding = emb_result.scalar_one_or_none()
                
                if embedding:
                    to_add_ids.append(str(img.id))
                    to_add_embeddings.append(json.loads(embedding.vector))
                    to_add_metadatas.append({
                        "file_hash": img.file_hash,
                        "file_path": img.file_path
                    })
        
        if to_add_ids:
            # Batch add to Chroma
            batch_size = 100
            for i in range(0, len(to_add_ids), batch_size):
                end = min(i + batch_size, len(to_add_ids))
                chroma_manager.add_embeddings(
                    ids=to_add_ids[i:end],
                    embeddings=to_add_embeddings[i:end],
                    metadatas=to_add_metadatas[i:end]
                )
            print(f"Added {len(to_add_ids)} missing items to Chroma")
        else:
            print("No missing items found to sync to Chroma")
