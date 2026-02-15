# Service modules
from .clustering import (
    create_strategy,
    perform_clustering,
    format_cluster_response,
)
from .embedding import (
    embed_text_async,
    embed_image_bytes_async,
    embed_images_with_progress,
    get_embedding_info,
)
from .image import (
    scan_directory,
    compute_file_hash,
    compute_corpus_hash,
    generate_thumbnail,
    get_image_metadata,
)
from .image_service import ImageService
from .search_service import SearchService
from .ingestion_job import IngestionJobService
from .image_ingestion import save_ingested_images
from .sync_service import sync_sqlite_to_chroma

# Export service classes for dependency injection
__all__ = [
    # Clustering
    "create_strategy",
    "perform_clustering",
    "format_cluster_response",
    # Embedding
    "embed_text_async",
    "embed_image_bytes_async",
    "embed_images_with_progress",
    "get_embedding_info",
    # Image utilities
    "scan_directory",
    "compute_file_hash",
    "compute_corpus_hash",
    "generate_thumbnail",
    "get_image_metadata",
    # Service classes (for dependency injection)
    "ImageService",
    "SearchService",
    "IngestionJobService",
    # Ingestion
    "save_ingested_images",
    # Sync
    "sync_sqlite_to_chroma",
]
