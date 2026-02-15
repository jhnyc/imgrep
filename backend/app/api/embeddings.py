from fastapi import APIRouter

from ..services.embedding import get_embedding_info

router = APIRouter(prefix="/api/embeddings", tags=["embeddings"])


@router.get("/info")
async def get_embeddings_info():
    """Get information about the current embedding backend"""
    return await get_embedding_info()


@router.get("/backend")
async def get_current_backend():
    """Get the current embedding backend name"""
    return {
        "backend": "siglip",
        "type": "local",
    }
