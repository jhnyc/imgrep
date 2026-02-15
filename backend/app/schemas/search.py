from typing import List, Optional
from pydantic import BaseModel


class SearchResult(BaseModel):
    image_id: int
    similarity: float
    thumbnail_url: str
    x: Optional[float] = None
    y: Optional[float] = None


class TextSearchRequest(BaseModel):
    query: str
    top_k: int = 20
    strategy: str = "hdbscan"
    projection_strategy: str = "umap"
    overlap_strategy: str = "none"


class TextSearchResponse(BaseModel):
    results: List[SearchResult]
    total: int


class ImageSearchResponse(BaseModel):
    results: List[SearchResult]
    total: int
