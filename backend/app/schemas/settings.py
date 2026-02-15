from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

class SettingsBase(BaseModel):
    embedding_model: str = "jina-clip-v2"
    batch_size: int = 12
    image_extensions: List[str] = ["jpg", "jpeg", "png", "webp"]
    auto_reindex: bool = True
    sync_frequency: str = "1h"

class SettingsCreate(SettingsBase):
    pass

class SettingsUpdate(SettingsBase):
    pass

class Settings(SettingsBase):
    id: int
    updated_at: datetime

    class Config:
        from_attributes = True
