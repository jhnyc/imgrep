"""Tests for clustering service."""
import numpy as np
import pytest

from app.clustering import (
    ClusteringStrategy,
    HDBSCANStrategy,
    KMeansStrategy,
    DBSCANStrategy,
    create_strategy,
    project_to_2d,
    normalize_coordinates,
    compute_cluster_centers,
)


def test_hdbscan_strategy_fit():
    """Test HDBSCAN clustering returns valid labels."""
    strategy = HDBSCANStrategy(min_cluster_size=2)

    # Create simple clusters
    embeddings = np.array([
        [0.0, 0.0],
        [0.1, 0.1],
        [5.0, 5.0],
        [5.1, 5.1],
    ])

    labels = strategy.fit(embeddings)

    assert len(labels) == 4
    assert strategy.get_name() == "hdbscan"


def test_kmeans_strategy_fit():
    """Test KMeans clustering with fixed k."""
    strategy = KMeansStrategy(n_clusters=2)

    embeddings = np.array([
        [0.0, 0.0],
        [0.1, 0.1],
        [5.0, 5.0],
        [5.1, 5.1],
    ])

    labels = strategy.fit(embeddings)

    assert len(labels) == 4
    assert set(labels).issubset({0, 1})
    assert strategy.get_name() == "kmeans"


def test_kmeans_strategy_auto_k():
    """Test KMeans with automatic K determination."""
    strategy = KMeansStrategy(n_clusters=None, max_k=5)

    embeddings = np.array([
        [0.0, 0.0],
        [0.1, 0.1],
        [5.0, 5.0],
        [5.1, 5.1],
        [10.0, 10.0],
        [10.1, 10.1],
    ])

    labels = strategy.fit(embeddings)

    assert len(labels) == 6
    assert strategy.n_clusters is not None
    assert strategy.n_clusters >= 1


def test_kmeans_strategy_small_dataset():
    """Test KMeans handles very small datasets."""
    strategy = KMeansStrategy(n_clusters=None)

    embeddings = np.array([[0.0], [1.0]])

    labels = strategy.fit(embeddings)

    assert len(labels) == 2
    # Should default to 1 cluster for tiny datasets
    assert strategy.n_clusters == 1


def test_dbscan_strategy_fit():
    """Test DBSCAN clustering."""
    strategy = DBSCANStrategy(eps=0.5, min_samples=2)

    embeddings = np.array([
        [0.0, 0.0],
        [0.1, 0.1],
        [5.0, 5.0],
        [5.1, 5.1],
    ])

    labels = strategy.fit(embeddings)

    assert len(labels) == 4
    assert strategy.get_name() == "dbscan"


def test_create_strategy():
    """Test strategy factory function."""
    hdbscan = create_strategy("hdbscan", {"min_cluster_size": 3})
    assert isinstance(hdbscan, HDBSCANStrategy)
    assert hdbscan.min_cluster_size == 3

    kmeans = create_strategy("kmeans", {"n_clusters": 5})
    assert isinstance(kmeans, KMeansStrategy)
    assert kmeans.n_clusters == 5

    dbscan = create_strategy("dbscan", {"eps": 0.3})
    assert isinstance(dbscan, DBSCANStrategy)
    assert dbscan.eps == 0.3


def test_create_strategy_invalid():
    """Test factory raises error for invalid strategy."""
    with pytest.raises(ValueError, match="Unknown strategy"):
        create_strategy("invalid_strategy")


def test_strategy_get_parameters():
    """Test get_parameters method."""
    hdbscan = HDBSCANStrategy(min_cluster_size=10, min_samples=5)
    params = hdbscan.get_parameters()
    assert params["min_cluster_size"] == 10
    assert params["min_samples"] == 5

    kmeans = KMeansStrategy(n_clusters=3, max_k=15)
    params = kmeans.get_parameters()
    assert params["n_clusters"] == 3
    assert params["max_k"] == 15


def test_project_to_2d_single_point():
    """Test 2D projection with single point."""
    embeddings = np.array([[0.1, 0.2, 0.3]])
    result = project_to_2d(embeddings)

    assert result.shape == (1, 2)
    assert np.array_equal(result, np.array([[0.0, 0.0]]))


def test_project_to_2d_two_points():
    """Test 2D projection with two points."""
    embeddings = np.array([[0.1, 0.2], [0.3, 0.4]])
    result = project_to_2d(embeddings)

    assert result.shape == (2, 2)


def test_project_to_2d_multiple_points():
    """Test 2D projection with multiple points."""
    embeddings = np.random.rand(10, 5)
    result = project_to_2d(embeddings)

    assert result.shape == (10, 2)


def test_normalize_coordinates_empty():
    """Test normalize with empty array."""
    coords = np.array([])
    result = normalize_coordinates(coords)

    assert result.shape == (0,)


def test_normalize_coordinates_single_point():
    """Test normalize with single point at origin."""
    coords = np.array([[0.0, 0.0]])
    result = normalize_coordinates(coords, canvas_size=1000.0)

    # Should return centered at origin
    assert np.allclose(result, [[0.0, 0.0]])


def test_normalize_coordinates_scaling():
    """Test coordinates are properly scaled to canvas."""
    coords = np.array([
        [0.0, 0.0],
        [100.0, 100.0],
    ])
    result = normalize_coordinates(coords, canvas_size=2000.0)

    # After centering and scaling, should fit within canvas
    center = np.mean(result, axis=0)
    assert np.allclose(center, [0.0, 0.0], atol=1e-10)

    # Max coordinate should be around canvas_size * 0.4
    max_range = np.max(np.abs(result))
    assert 0 < max_range <= 2000.0 * 0.45


def test_compute_cluster_centers():
    """Test computing cluster centers."""
    coordinates = np.array([
        [0.0, 0.0],  # cluster 0
        [2.0, 0.0],  # cluster 0
        [10.0, 10.0],  # cluster 1
        [12.0, 12.0],  # cluster 1
        [-1.0, -1.0],  # noise (-1)
    ])
    labels = np.array([0, 0, 1, 1, -1])

    centers = compute_cluster_centers(coordinates, labels)

    assert len(centers) == 2
    assert 0 in centers
    assert 1 in centers
    assert -1 not in centers  # Noise should not have a center

    # Cluster 0 center should be around (1, 0)
    assert abs(centers[0]["x"] - 1.0) < 0.01
    assert abs(centers[0]["y"] - 0.0) < 0.01
    assert centers[0]["count"] == 2

    # Cluster 1 center should be around (11, 11)
    assert abs(centers[1]["x"] - 11.0) < 0.01
    assert abs(centers[1]["y"] - 11.0) < 0.01
    assert centers[1]["count"] == 2


def test_compute_cluster_centers_all_noise():
    """Test centers with only noise points."""
    coordinates = np.array([
        [0.0, 0.0],
        [1.0, 1.0],
    ])
    labels = np.array([-1, -1])

    centers = compute_cluster_centers(coordinates, labels)

    assert len(centers) == 0
