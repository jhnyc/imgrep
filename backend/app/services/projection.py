import pickle
from typing import Any, Tuple, Optional
import numpy as np
import umap
from ..core.config import MODELS_DIR

def save_model(model: Any, filename: str) -> str:
    """Save model to disk using pickle"""
    path = MODELS_DIR / filename
    with open(path, "wb") as f:
        pickle.dump(model, f)
    return str(path)


def load_model(filename: str) -> Optional[Any]:
    """Load model from disk"""
    path = MODELS_DIR / filename
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        print(f"Failed to load model from {path}: {e}")
        return None

from abc import ABC, abstractmethod

class ProjectionStrategy(ABC):
    """Abstract base class for 2D projection strategies"""
    
    @abstractmethod
    def project(self, embeddings: np.ndarray, existing_model: Any = None, **kwargs) -> Tuple[np.ndarray, Any]:
        """
        Project embeddings to 2D.
        Returns: (coordinates, model)
        """
        pass

class PCAStrategy(ProjectionStrategy):
    def project(self, embeddings: np.ndarray, existing_model: Any = None, **kwargs) -> Tuple[np.ndarray, Any]:
        from sklearn.decomposition import PCA
        
        if existing_model:
            try:
                return existing_model.transform(embeddings), existing_model
            except Exception as e:
                print(f"PCA transform failed, falling back to fit: {e}")
        
        pca = PCA(n_components=2, random_state=42)
        return pca.fit_transform(embeddings), pca

class TSNEStrategy(ProjectionStrategy):
    def project(self, embeddings: np.ndarray, existing_model: Any = None, **kwargs) -> Tuple[np.ndarray, Any]:
        from sklearn.manifold import TSNE
        n_samples = len(embeddings)
        perplexity = min(30, max(1, n_samples - 1))
        
        reducer = TSNE(
            n_components=2,
            perplexity=perplexity,
            random_state=42,
            init='pca',
            learning_rate='auto'
        )
        return reducer.fit_transform(embeddings), None

class UMAPStrategy(ProjectionStrategy):
    def project(self, embeddings: np.ndarray, existing_model: Any = None, **kwargs) -> Tuple[np.ndarray, Any]:
        n_samples = len(embeddings)
        n_neighbors = kwargs.get('n_neighbors', 15)
        min_dist = kwargs.get('min_dist', 0.1)
        
        adjusted_neighbors = min(n_neighbors, n_samples - 1)
        
        if existing_model:
            try:
                return existing_model.transform(embeddings), existing_model
            except Exception as e:
                print(f"UMAP transform failed, falling back to fit: {e}")

        reducer = umap.UMAP(
            n_components=2,
            n_neighbors=adjusted_neighbors,
            min_dist=min_dist,
            random_state=42,
            metric="cosine",
        )

        try:
            return reducer.fit_transform(embeddings), reducer
        except Exception as e:
            print(f"UMAP fit failed: {e}. Falling back to PCA.")
            return PCAStrategy().project(embeddings)

def get_projection_strategy(strategy_name: str) -> ProjectionStrategy:
    strategies = {
        "pca": PCAStrategy,
        "tsne": TSNEStrategy,
        "umap": UMAPStrategy
    }
    strategy_class = strategies.get(strategy_name, UMAPStrategy)
    return strategy_class()

def project_to_2d(
    embeddings: np.ndarray, 
    strategy: str = "umap", 
    n_neighbors: int = 15, 
    min_dist: float = 0.1,
    existing_model: Any = None
) -> Tuple[np.ndarray, Any]:
    """
    Project embeddings to 2D for canvas positioning.
    Supported strategies: 'umap', 'pca', 'tsne'
    Returns: (coordinates, model)
    """
    n_samples = len(embeddings)

    # Handle edge cases
    if n_samples <= 2:
        # Simple linear layout for very small datasets
        if n_samples == 1:
            return np.array([[0.0, 0.0]]), None
        return np.array([[0.0, 0.0], [100.0, 0.0]]), None

    projection_strategy = get_projection_strategy(strategy)
    return projection_strategy.project(
        embeddings, 
        existing_model=existing_model, 
        n_neighbors=n_neighbors, 
        min_dist=min_dist
    )
