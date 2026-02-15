from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class JobStatus(BaseModel):
    job_id: str
    status: str  # pending, processing, completed, error
    progress: float
    total: int
    processed: int
    errors: List[str]
    directory_path: Optional[str] = None


class JobStatusResponse(JobStatus):
    """Alias for JobStatus for backwards compatibility"""
    pass


class JobListItem(BaseModel):
    job_id: str
    status: str
    progress: float
    total: int
    processed: int
    errors: List[str]
    directory_path: Optional[str] = None


class JobListResponse(BaseModel):
    jobs: List[JobListItem]


class AddDirectoryRequest(BaseModel):
    path: str


class TrackedDirectoryResponse(BaseModel):
    """Response model for a tracked directory"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    path: str
    sync_strategy: str
    is_active: bool
    last_synced_at: Optional[str]
    last_error: Optional[str]
    sync_interval_seconds: int
    created_at: str
    file_count: Optional[int] = None


class TrackedDirectoryListResponse(BaseModel):
    """Response model for list of tracked directories"""
    directories: List[TrackedDirectoryResponse]


class AddTrackedDirectoryRequest(BaseModel):
    """Request model for adding a tracked directory"""
    path: str
    sync_strategy: str = "snapshot"  # "snapshot" or "merkle"
    sync_interval_seconds: int = 300  # 5 minutes default


class SyncResultResponse(BaseModel):
    """Response model for sync operation result"""
    tracked_directory_id: int
    added: List[str]
    modified: List[str]
    deleted: List[str]
    unchanged: int
    errors: List[str]
    sync_duration_seconds: float
    strategy_used: str
