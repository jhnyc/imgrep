from typing import List, Optional
from pydantic import BaseModel


class ImageDetails(BaseModel):
    id: int
    file_path: str
    file_name: str
    width: Optional[int]
    height: Optional[int]
    thumbnail_url: str
    cluster_label: Optional[int] = None


class ImageListItem(BaseModel):
    id: int
    file_name: str
    thumbnail_url: str


class ImageListResponse(BaseModel):
    images: List[ImageListItem]
    total: int
