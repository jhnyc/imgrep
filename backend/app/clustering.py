import json
from abc import ABC, abstractmethod
from typing import Any, Optional
import numpy as np
import umap
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics import silhouette_score
import hdbscan


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


def project_to_2d(embeddings: np.ndarray, n_neighbors: int = 15, min_dist: float = 0.1) -> np.ndarray:
    """
    Project embeddings to 2D using UMAP for canvas positioning.
    Returns: Array of shape (n_samples, 2) with x, y coordinates
    """
    n_samples = len(embeddings)

    # Handle edge cases
    if n_samples <= 2:
        # Simple linear layout for very small datasets
        if n_samples == 1:
            return np.array([[0.0, 0.0]])
        return np.array([[0.0, 0.0], [100.0, 0.0]])

    # Adjust n_neighbors based on dataset size
    adjusted_neighbors = min(n_neighbors, n_samples - 1)

    reducer = umap.UMAP(
        n_components=2,
        n_neighbors=adjusted_neighbors,
        min_dist=min_dist,
        random_state=42,
        metric="cosine",
    )

    # UMAP can fail on very small or degenerate datasets
    try:
        coordinates = reducer.fit_transform(embeddings)
        return coordinates
    except Exception:
        # Fallback to simple scaling if UMAP fails
        # Use first two dimensions with PCA-like scaling
        from sklearn.decomposition import PCA
        pca = PCA(n_components=2, random_state=42)
        return pca.fit_transform(embeddings)


def normalize_coordinates(coordinates: np.ndarray, canvas_size: float = None) -> np.ndarray:
    """
    Normalize coordinates to fit within canvas.
    Returns coordinates centered on canvas with appropriate scale.
    """
    from .constants import CANVAS_SIZE

    if canvas_size is None:
        canvas_size = CANVAS_SIZE
    """
    Normalize coordinates to fit within canvas.
    Returns coordinates centered on canvas with appropriate scale.
    """
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
) -> dict[int, dict]:
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
