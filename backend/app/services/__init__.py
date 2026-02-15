# Service modules
from .clustering import (
    create_strategy,
    perform_clustering,
    format_cluster_response,
)
from .embedding import (
    embed_text_async,
    embed_image_bytes_async,
    embed_images_batch_async,
    embed_images_with_progress,
    get_embedding_info,
    get_backend,
    is_jina_backend,
    is_siglip_backend,
)
from .image import (
    scan_directory,
    compute_file_hash,
    compute_corpus_hash,
    generate_thumbnail,
    get_image_metadata,
    get_thumbnail_url,
)
from .chroma import chroma_manager
from .ingestion import directory_service, save_ingested_images

__all__ = [
    # Clustering
    "create_strategy",
    "perform_clustering",
    "format_cluster_response",
    # Embedding
    "embed_text_async",
    "embed_image_bytes_async",
    "embed_images_batch_async",
    "embed_images_with_progress",
    "get_embedding_info",
    "get_backend",
    "is_jina_backend",
    "is_siglip_backend",
    # Image
    "scan_directory",
    "compute_file_hash",
    "compute_corpus_hash",
    "generate_thumbnail",
    "get_image_metadata",
    "get_thumbnail_url",
    # Chroma
    "chroma_manager",
    # Ingestion
    "directory_service",
    "save_ingested_images",
]
