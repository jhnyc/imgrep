import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..database import (
    AsyncSessionLocal,
    get_all_image_ids,
    get_all_embeddings,
    get_current_clustering_run,
    set_current_clustering_run,
)
from ..models import ClusteringRun, ClusterAssignment, ClusterMetadata, Image
from ..clustering import (
    create_strategy,
    project_to_2d,
    normalize_coordinates,
    compute_cluster_centers,
)
from ..image_processor import compute_corpus_hash

router = APIRouter(prefix="/api/clusters", tags=["clusters"])


class RecomputeRequest(BaseModel):
    strategy: str = "hdbscan"
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
    clusters: list[ClusterNode]
    images: list[ImagePosition]
    total_images: int


async def perform_clustering(
    strategy_name: str,
    parameters: Optional[dict],
    corpus_hash: str
) -> ClusteringRun:
    """Perform clustering and save results to database"""
    # Get all embeddings
    image_embeddings = await get_all_embeddings()
    if not image_embeddings:
        raise HTTPException(status_code=400, detail="No images with embeddings found")

    image_ids = list(image_embeddings.keys())
    embeddings_array = [image_embeddings[id] for id in image_ids]

    import numpy as np
    embeddings_np = np.array(embeddings_array)

    # Run clustering
    strategy = create_strategy(strategy_name, parameters)
    labels = strategy.fit(embeddings_np)

    # Project to 2D
    coordinates = project_to_2d(embeddings_np)
    coordinates = normalize_coordinates(coordinates, canvas_size=2000.0)

    # Compute cluster centers
    cluster_centers = compute_cluster_centers(coordinates, labels)

    # Save to database
    async with AsyncSessionLocal() as session:
        # Create clustering run
        run = ClusteringRun(
            strategy=strategy_name,
            image_corpus_hash=corpus_hash,
            parameters=json.dumps(parameters or {}),
            is_current=True,
        )
        session.add(run)
        await session.flush()

        run_id = run.id

        # Save cluster assignments
        for i, (img_id, label) in enumerate(zip(image_ids, labels)):
            assignment = ClusterAssignment(
                clustering_run_id=run_id,
                image_id=img_id,
                cluster_label=int(label) if label >= 0 else None,
            )
            session.add(assignment)

        # Save cluster metadata
        for label, center_data in cluster_centers.items():
            metadata = ClusterMetadata(
                clustering_run_id=run_id,
                cluster_label=label,
                center_x=center_data["x"],
                center_y=center_data["y"],
                image_count=center_data["count"],
            )
            session.add(metadata)

        await session.commit()
        await session.refresh(run)

    # Set as current for this strategy
    await set_current_clustering_run(run_id, strategy_name)

    return run


@router.get("", response_model=ClustersResponse)
async def get_clusters(
    strategy: str = Query("hdbscan", description="Clustering strategy"),
    force_recompute: bool = Query(False, description="Force re-clustering"),
):
    """Get clusters for images. Auto-reclusters if corpus has changed."""
    # Get current corpus
    image_ids = await get_all_image_ids()
    if not image_ids:
        return ClustersResponse(
            clustering_run_id=0,
            strategy=strategy,
            clusters=[],
            images=[],
            total_images=0,
        )

    corpus_hash = compute_corpus_hash(image_ids)

    # Check for existing clustering run
    if not force_recompute:
        existing_run = await get_current_clustering_run(strategy, corpus_hash)
        if existing_run:
            return await format_cluster_response(existing_run)

    # Need to run clustering
    run = await perform_clustering(strategy, None, corpus_hash)
    return await format_cluster_response(run)


@router.post("/recompute", response_model=ClustersResponse)
async def recompute_clusters(request: RecomputeRequest):
    """Force re-clustering with specific parameters"""
    image_ids = await get_all_image_ids()
    if not image_ids:
        return ClustersResponse(
            clustering_run_id=0,
            strategy=request.strategy,
            clusters=[],
            images=[],
            total_images=0,
        )

    corpus_hash = compute_corpus_hash(image_ids)

    run = await perform_clustering(request.strategy, request.parameters, corpus_hash)
    return await format_cluster_response(run)


async def format_cluster_response(run: ClusteringRun) -> ClustersResponse:
    """Format clustering run for API response"""
    async with AsyncSessionLocal() as session:
        # Get cluster metadata
        from sqlalchemy import select
        result = await session.execute(
            select(ClusterMetadata).where(ClusterMetadata.clustering_run_id == run.id)
        )
        cluster_metadata_rows = result.scalars().all()

        # Get image assignments with image data
        result = await session.execute(
            select(ClusterAssignment, Image)
            .join(Image, ClusterAssignment.image_id == Image.id)
            .where(ClusterAssignment.clustering_run_id == run.id)
        )
        assignment_rows = result.all()

        # Get image coordinates (we need to store them separately or recompute)
        # For now, let's store positions in a separate query or recompute
        # We'll need to add position storage to the database

        # Get embeddings for re-computing positions
        image_embeddings = await get_all_embeddings()

        # Recompute 2D positions
        import numpy as np
        embeddings_list = [image_embeddings[row[0].image_id] for row in assignment_rows]
        if embeddings_list:
            embeddings_np = np.array(embeddings_list)
            coordinates = project_to_2d(embeddings_np)
            coordinates = normalize_coordinates(coordinates, canvas_size=2000.0)
        else:
            coordinates = np.array([])

        clusters = [
            ClusterNode(
                id=row.cluster_label,
                x=row.center_x or 0.0,
                y=row.center_y or 0.0,
                image_count=row.image_count,
            )
            for row in cluster_metadata_rows
        ]

        images = []
        for i, (assignment, image) in enumerate(assignment_rows):
            thumbnail_url = f"/api/thumbnails/{image.thumbnail_path}" if image.thumbnail_path else ""
            x = float(coordinates[i][0]) if i < len(coordinates) else 0.0
            y = float(coordinates[i][1]) if i < len(coordinates) else 0.0
            images.append(
                ImagePosition(
                    id=image.id,
                    x=x,
                    y=y,
                    cluster_label=assignment.cluster_label,
                    thumbnail_url=thumbnail_url,
                )
            )

        return ClustersResponse(
            clustering_run_id=run.id,
            strategy=run.strategy,
            clusters=clusters,
            images=images,
            total_images=len(images),
        )


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
        ]
    }
