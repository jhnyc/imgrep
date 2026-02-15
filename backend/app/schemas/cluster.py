from typing import Optional, List
from pydantic import BaseModel

class RecomputeRequest(BaseModel):
    strategy: str = "hdbscan"
    projection_strategy: str = "umap"
    overlap_strategy: str = "none"
    parameters: Optional[dict] = None


class ClusterNode(BaseModel):
    id: int  # cluster label
    x: float
    y: float
    image_count: int


class ImagePosition(BaseModel):
    id: int
    x: float
    y: float
    cluster_label: Optional[int]
    thumbnail_url: str


class ClustersResponse(BaseModel):
    clustering_run_id: int
    strategy: str
    projection_strategy: str
    overlap_strategy: str
    clusters: List[ClusterNode]
    images: List[ImagePosition]
    total_images: int
