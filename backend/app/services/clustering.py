import json
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, List, Tuple
from datetime import datetime
import numpy as np
import numpy as np
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics import silhouette_score
import hdbscan

from fastapi import HTTPException
from sqlalchemy import select

from ..models.sql import ClusteringRun, ClusterAssignment, ClusterMetadata, Image
from ..core.database import (
    AsyncSessionLocal,
    get_all_image_ids,
    get_all_embeddings,
    get_current_clustering_run,
    set_current_clustering_run,
)
from ..schemas.cluster import ClustersResponse, ClusterNode, ImagePosition
from ..constants import PROJECTION_RETRAIN_THRESHOLD
from .projection import project_to_2d, save_model, load_model
import os


# =============================================================================
# Strategy Classes
# =============================================================================

class ClusteringStrategy(ABC):
    """Abstract base class for clustering strategies"""

    @abstractmethod
    def fit(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Fit clustering model and return cluster labels.
        Returns: Array of cluster labels (-1 for noise/outliers)
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return strategy name"""
        pass


class HDBSCANStrategy(ClusteringStrategy):
    """
    HDBSCAN clustering - density-based, automatic cluster count.
    Parameters:
    - min_cluster_size: Minimum size of clusters (default: 5)
    - min_samples: How conservative clustering is (default: None -> same as min_cluster_size)
    """

    def __init__(self, min_cluster_size: int = 5, min_samples: Optional[int] = None):
        self.min_cluster_size = min_cluster_size
        self.min_samples = min_samples
        self.clusterer = None

    def fit(self, embeddings: np.ndarray) -> np.ndarray:
        self.clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            min_samples=self.min_samples,
            prediction_data=True,
        )
        return self.clusterer.fit_predict(embeddings)

    def get_name(self) -> str:
        return "hdbscan"

    def get_parameters(self) -> dict:
        return {
            "min_cluster_size": self.min_cluster_size,
            "min_samples": self.min_samples,
        }


class KMeansStrategy(ClusteringStrategy):
    """
    K-Means clustering with automatic K determination via silhouette score.
    Parameters:
    - n_clusters: Number of clusters (None for auto-determination)
    - max_k: Maximum K to try when auto-determining (default: 20)
    """

    def __init__(self, n_clusters: Optional[int] = None, max_k: int = 20):
        self.n_clusters = n_clusters
        self.max_k = max_k
        self.clusterer = None

    def fit(self, embeddings: np.ndarray) -> np.ndarray:
        # Auto-determine K if not specified
        if self.n_clusters is None:
            self.n_clusters = self._find_optimal_k(embeddings)

        self.clusterer = KMeans(n_clusters=self.n_clusters, random_state=42, n_init=10)
        return self.clusterer.fit_predict(embeddings)

    def _find_optimal_k(self, embeddings: np.ndarray) -> int:
        """Find optimal K using silhouette score"""
        n_samples = len(embeddings)
        max_possible_k = min(self.max_k, n_samples - 1, max(2, n_samples // 10))

        if n_samples < 4:
            return 1

        best_k = 2
        best_score = -1

        for k in range(2, max_possible_k + 1):
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(embeddings)

            # Skip if all samples in one cluster
            if len(set(labels)) < 2:
                continue

            score = silhouette_score(embeddings, labels)
            if score > best_score:
                best_score = score
                best_k = k

        return best_k

    def get_name(self) -> str:
        return "kmeans"

    def get_parameters(self) -> dict:
        return {
            "n_clusters": self.n_clusters,
            "max_k": self.max_k,
        }


class DBSCANStrategy(ClusteringStrategy):
    """
    DBSCAN clustering - density-based with fixed epsilon.
    Parameters:
    - eps: Maximum distance between samples (default: 0.5)
    - min_samples: Minimum samples in neighborhood (default: 5)
    """

    def __init__(self, eps: float = 0.5, min_samples: int = 5):
        self.eps = eps
        self.min_samples = min_samples
        self.clusterer = None

    def fit(self, embeddings: np.ndarray) -> np.ndarray:
        self.clusterer = DBSCAN(eps=self.eps, min_samples=self.min_samples)
        return self.clusterer.fit_predict(embeddings)

    def get_name(self) -> str:
        return "dbscan"

    def get_parameters(self) -> dict:
        return {
            "eps": self.eps,
            "min_samples": self.min_samples,
        }


def create_strategy(strategy_name: str, parameters: Optional[dict] = None) -> ClusteringStrategy:
    """Factory function to create clustering strategy"""
    parameters = parameters or {}

    strategies = {
        "hdbscan": HDBSCANStrategy,
        "kmeans": KMeansStrategy,
        "dbscan": DBSCANStrategy,
    }

    if strategy_name not in strategies:
        raise ValueError(f"Unknown strategy: {strategy_name}. Available: {list(strategies.keys())}")

    return strategies[strategy_name](**parameters)



# =============================================================================
# Coordinate Post-Processing Strategies
# =============================================================================

class CoordinatePostProcessor(ABC):
    """Abstract base class for coordinate post-processing (e.g., overlap reduction)"""

    @abstractmethod
    def process(self, coordinates: np.ndarray) -> np.ndarray:
        """
        Process coordinates and return adjusted ones.
        Args:
            coordinates: Array of shape (n_samples, 2)
        Returns:
            Adjusted array of same shape
        """
        pass


class NoneProcessor(CoordinatePostProcessor):
    """No post-processing"""

    def process(self, coordinates: np.ndarray) -> np.ndarray:
        return coordinates


class JitterProcessor(CoordinatePostProcessor):
    """Random jittering to reduce overlap"""

    def __init__(self, jitter_amount: float = 10.0, **kwargs):
        self.amount = jitter_amount

    def process(self, coordinates: np.ndarray) -> np.ndarray:
        if len(coordinates) == 0:
            return coordinates
        
        jitter = np.random.uniform(-self.amount, self.amount, size=coordinates.shape)
        return coordinates + jitter


def create_post_processor(strategy_name: str, parameters: Optional[dict] = None) -> CoordinatePostProcessor:
    """Factory function to create post-processor"""
    parameters = parameters or {}
    
    processors = {
        "none": NoneProcessor,
        "jitter": JitterProcessor,
    }
    
    if strategy_name not in processors:
        return NoneProcessor()
        
    return processors[strategy_name](**parameters)





def normalize_coordinates(coordinates: np.ndarray, canvas_size: float = None) -> np.ndarray:
    """
    Normalize coordinates to fit within canvas.
    Returns coordinates centered on canvas with appropriate scale.
    """
    from ..core.config import CANVAS_SIZE

    if canvas_size is None:
        canvas_size = CANVAS_SIZE

    if len(coordinates) == 0:
        return coordinates

    # Center the coordinates
    center = np.mean(coordinates, axis=0)
    centered = coordinates - center

    # Scale to fit canvas
    max_range = np.max(np.abs(centered))
    if max_range > 0:
        scale = (canvas_size * 0.4) / max_range
        scaled = centered * scale
    else:
        scaled = centered

    return scaled


def compute_cluster_centers(
    coordinates: np.ndarray,
    labels: np.ndarray
) -> Dict[int, dict]:
    """
    Compute cluster centers for visualization.
    Returns: {cluster_label: {"x": float, "y": float, "count": int}}
    """
    unique_labels = set(labels)
    centers = {}

    for label in unique_labels:
        if label == -1:  # Noise points
            continue

        mask = labels == label
        cluster_coords = coordinates[mask]
        centers[label] = {
            "x": float(np.mean(cluster_coords[:, 0])),
            "y": float(np.mean(cluster_coords[:, 1])),
            "count": int(np.sum(mask)),
        }

    return centers


# =============================================================================
# Orchestration Functions
# =============================================================================

async def perform_clustering(
    strategy_name: str,
    parameters: Optional[dict],
    corpus_hash: str,
    projection_strategy: str = "umap",
    overlap_strategy: str = "none"
) -> ClusteringRun:
    """
    Perform clustering and save results to database.

    Args:
        strategy_name: Name of the strategy to use
        parameters: Additional parameters for the strategy
        corpus_hash: Hash representing the current state of image corpus

    Returns:
        ClusteringRun object
    """
    parameters = parameters or {}
    
    # Get all embeddings
    image_embeddings = await get_all_embeddings()
    if not image_embeddings:
        raise HTTPException(status_code=400, detail="No images with embeddings found")

    image_ids = list(image_embeddings.keys())
    embeddings_array = [image_embeddings[id] for id in image_ids]
    embeddings_np = np.array(embeddings_array)
    current_count = len(image_ids)

    # Check for previous run to potentially reuse model
    existing_model = None
    reused_model_path = None
    
    # Threshold for re-training (e.g., 20% growth)
    RETRAIN_THRESHOLD = PROJECTION_RETRAIN_THRESHOLD

    async with AsyncSessionLocal() as session:
        # Find latest run with same configuration
        query = select(ClusteringRun).where(
            ClusteringRun.strategy == strategy_name,
            ClusteringRun.projection_strategy == projection_strategy,
            ClusteringRun.overlap_strategy == overlap_strategy
        ).order_by(ClusteringRun.created_at.desc()).limit(1)
        
        result = await session.execute(query)
        last_run = result.scalar_one_or_none()
        
        if last_run:
            try:
                last_params = json.loads(last_run.parameters or "{}")
                last_model_path = last_params.get("model_path")
                last_training_size = last_params.get("training_corpus_size", 0)
                
                # Check if we should reuse
                if last_model_path and last_training_size > 0:
                    growth = (current_count - last_training_size) / last_training_size
                    
                    if growth <= RETRAIN_THRESHOLD and projection_strategy != "tsne":
                        print(f"Dataset growth {growth:.2%} within threshold. Attempting to reuse model from {last_model_path}")
                        loaded = load_model(last_model_path)
                        if loaded:
                            existing_model = loaded
                            reused_model_path = last_model_path
                        else:
                            print("Model file missing, forcing retrain.")
                    else:
                        print(f"Dataset growth {growth:.2%} > threshold {RETRAIN_THRESHOLD:.2%} (or tsne). Forcing retrain.")
            except Exception as e:
                print(f"Error checking previous run: {e}")

    # Run clustering (labels)
    # Note: Clustering (HDBSCAN/KMeans) is also usually fit-predict. 
    # For now we only optimized Projection (UMAP/PCA) persistence as it's the visualization bottleneck.
    strategy = create_strategy(strategy_name, parameters)
    labels = strategy.fit(embeddings_np)

    # Project to 2D
    coordinates, model = project_to_2d(
        embeddings_np, 
        strategy=projection_strategy, 
        existing_model=existing_model
    )
    
    # Save model if new and valid
    model_path = reused_model_path
    if model and model != existing_model and projection_strategy != "tsne":
        # Generate filename
        filename = f"projection_{projection_strategy}_{corpus_hash}_{int(datetime.now().timestamp())}.pkl"
        try:
            model_path = save_model(model, filename)
            # Clean up old models? TODO
        except Exception as e:
            print(f"Failed to save model: {e}")

    coordinates = normalize_coordinates(coordinates, canvas_size=2000.0)

    # Post-process coordinates
    post_processor = create_post_processor(overlap_strategy, parameters)
    coordinates = post_processor.process(coordinates)

    # Compute cluster centers
    cluster_centers = compute_cluster_centers(coordinates, labels)
    
    # Update parameters with model info
    run_parameters = parameters.copy()
    if model_path:
        run_parameters["model_path"] = os.path.basename(model_path)
    run_parameters["training_corpus_size"] = current_count

    # Save to database
    async with AsyncSessionLocal() as session:
        # Create clustering run
        run = ClusteringRun(
            strategy=strategy_name,
            projection_strategy=projection_strategy,
            overlap_strategy=overlap_strategy,
            image_corpus_hash=corpus_hash,
            parameters=json.dumps(run_parameters),
            is_current=True,
        )
        session.add(run)
        await session.flush()

        run_id = run.id

        # Save cluster assignments with coordinates
        for i, (img_id, label) in enumerate(zip(image_ids, labels)):
            assignment = ClusterAssignment(
                clustering_run_id=run_id,
                image_id=img_id,
                cluster_label=int(label) if label >= 0 else None,
                x=float(coordinates[i][0]),
                y=float(coordinates[i][1]),
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

    # Set as current for this strategy and projection
    await set_current_clustering_run(run_id, strategy_name, projection_strategy, overlap_strategy)

    return run


async def format_cluster_response(run: ClusteringRun) -> ClustersResponse:
    """Format clustering run for API response"""
    async with AsyncSessionLocal() as session:
        # Get cluster metadata
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

        clusters = []
        for row in cluster_metadata_rows:
            # Handle potential bytes from DB driver
            cluster_id = row.cluster_label
            if isinstance(cluster_id, bytes):
                cluster_id = int.from_bytes(cluster_id, byteorder='little')
            
            clusters.append(ClusterNode(
                id=cluster_id,
                x=row.center_x or 0.0,
                y=row.center_y or 0.0,
                image_count=row.image_count,
            ))

        images = []
        for assignment, image in assignment_rows:
            thumbnail_url = f"/api/thumbnails/{image.thumbnail_path}" if image.thumbnail_path else ""
            # Use stored coordinates if available, otherwise fall back to 0,0
            x = assignment.x if assignment.x is not None else 0.0
            y = assignment.y if assignment.y is not None else 0.0
            cluster_label = assignment.cluster_label
            if isinstance(cluster_label, bytes):
                cluster_label = int.from_bytes(cluster_label, byteorder='little')

            images.append(
                ImagePosition(
                    id=image.id,
                    x=x,
                    y=y,
                    cluster_label=cluster_label,
                    thumbnail_url=thumbnail_url,
                )
            )

        return ClustersResponse(
            clustering_run_id=run.id,
            strategy=run.strategy,
            projection_strategy=run.projection_strategy,
            overlap_strategy=run.overlap_strategy,
            clusters=clusters,
            images=images,
            total_images=len(images),
        )
