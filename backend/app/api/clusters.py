from fastapi import APIRouter, Query

from ..core.database import (
    get_all_image_ids,
    get_current_clustering_run,
    get_all_clustering_runs_for_corpus,
)
from ..services.image import compute_corpus_hash
from ..schemas.cluster import RecomputeRequest, ClustersResponse
from ..services.clustering import perform_clustering, format_cluster_response

router = APIRouter(prefix="/api/clusters", tags=["clusters"])


@router.get("", response_model=ClustersResponse)
async def get_clusters(
    strategy: str = Query("hdbscan", description="Clustering strategy"),
    projection_strategy: str = Query("umap", description="Projection strategy (umap, pca, tsne)"),
    overlap_strategy: str = Query("none", description="Overlap reduction strategy (none, jitter)"),
    force_recompute: bool = Query(False, description="Force re-clustering"),
):
    """Get clusters for images. Auto-reclusters if corpus has changed."""
    # Get current corpus
    image_ids = await get_all_image_ids()
    if not image_ids:
        return ClustersResponse(
            clustering_run_id=0,
            strategy=strategy,
            projection_strategy=projection_strategy,
            overlap_strategy=overlap_strategy,
            clusters=[],
            images=[],
            total_images=0,
        )

    corpus_hash = compute_corpus_hash(image_ids)

    # Check for existing clustering run
    if not force_recompute:
        existing_run = await get_current_clustering_run(strategy, projection_strategy, overlap_strategy, corpus_hash)
        if existing_run:
            return await format_cluster_response(existing_run)

    # Need to run clustering
    run = await perform_clustering(strategy, None, corpus_hash, projection_strategy, overlap_strategy)
    return await format_cluster_response(run)


@router.post("/recompute", response_model=ClustersResponse)
async def recompute_clusters(request: RecomputeRequest):
    """Force re-clustering with specific parameters"""
    image_ids = await get_all_image_ids()
    if not image_ids:
        return ClustersResponse(
            clustering_run_id=0,
            strategy=request.strategy,
            projection_strategy=request.projection_strategy,
            clusters=[],
            images=[],
            total_images=0,
        )

    corpus_hash = compute_corpus_hash(image_ids)

    run = await perform_clustering(
        request.strategy, 
        request.parameters, 
        corpus_hash, 
        request.projection_strategy
    )
    return await format_cluster_response(run)


@router.get("/status")
async def get_clustering_status():
    """Get status of all clustering/projection combinations for current corpus"""
    image_ids = await get_all_image_ids()
    if not image_ids:
        return {"built_combinations": []}

    corpus_hash = compute_corpus_hash(image_ids)
    runs = await get_all_clustering_runs_for_corpus(corpus_hash)
    
    built = [
        {
            "strategy": run.strategy, 
            "projection_strategy": run.projection_strategy,
            "overlap_strategy": run.overlap_strategy
        }
        for run in runs
    ]
    
    return {"built_combinations": built}


@router.get("/strategies")
async def list_strategies():
    """List available clustering strategies"""
    return {
        "strategies": [
            {
                "name": "hdbscan",
                "description": "Density-based clustering with automatic cluster detection",
                "default": True,
            },
            {
                "name": "kmeans",
                "description": "K-means clustering with automatic K determination",
                "default": False,
            },
            {
                "name": "dbscan",
                "description": "DBSCAN density-based clustering",
                "default": False,
            },
        ],
        "projection_strategies": [
            {
                "name": "umap",
                "description": "UMAP (Uniform Manifold Approximation and Projection)",
                "default": True,
            },
            {
                "name": "pca",
                "description": "PCA (Principal Component Analysis)",
                "default": False,
            },
            {
                "name": "tsne",
                "description": "t-SNE (t-Distributed Stochastic Neighbor Embedding)",
                "default": False,
            },
        ],
        "overlap_strategies": [
            {
                "name": "none",
                "description": "No overlap reduction",
                "default": True,
            },
            {
                "name": "jitter",
                "description": "Random jittering to separate similar images",
                "default": False,
            },
        ]
    }
