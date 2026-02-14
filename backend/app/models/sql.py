from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(primary_key=True)
    vector: Mapped[str] = mapped_column(Text)
    model_name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    images: Mapped[list["Image"]] = relationship(back_populates="embedding")


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    file_path: Mapped[str] = mapped_column(String(1024))
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    embedding_id: Mapped[Optional[int]] = mapped_column(ForeignKey("embeddings.id"), nullable=True)
    embedding_status: Mapped[str] = mapped_column(String(20), default="pending")

    embedding: Mapped[Optional["Embedding"]] = relationship(back_populates="images")


class ClusteringRun(Base):
    __tablename__ = "clustering_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy: Mapped[str] = mapped_column(String(50), index=True)
    projection_strategy: Mapped[str] = mapped_column(String(50), index=True, default="umap")
    overlap_strategy: Mapped[str] = mapped_column(String(50), index=True, default="none")
    image_corpus_hash: Mapped[str] = mapped_column(String(64), index=True)
    parameters: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    assignments: Mapped[list["ClusterAssignment"]] = relationship(
        back_populates="clustering_run", cascade="all, delete-orphan"
    )
    cluster_metadata_list: Mapped[list["ClusterMetadata"]] = relationship(
        back_populates="clustering_run", cascade="all, delete-orphan"
    )


class ClusterAssignment(Base):
    __tablename__ = "cluster_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    clustering_run_id: Mapped[int] = mapped_column(ForeignKey("clustering_runs.id"), index=True)
    image_id: Mapped[int] = mapped_column(ForeignKey("images.id"), index=True)
    cluster_label: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    clustering_run: Mapped["ClusteringRun"] = relationship(back_populates="assignments")


class ClusterMetadata(Base):
    __tablename__ = "cluster_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    clustering_run_id: Mapped[int] = mapped_column(ForeignKey("clustering_runs.id"))
    cluster_label: Mapped[int] = mapped_column(Integer)
    center_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    center_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    image_count: Mapped[int] = mapped_column(Integer, default=0)

    clustering_run: Mapped["ClusteringRun"] = relationship(back_populates="cluster_metadata_list")


class TrackedDirectory(Base):
    __tablename__ = "tracked_directories"

    id: Mapped[int] = mapped_column(primary_key=True)
    path: Mapped[str] = mapped_column(String(1024), unique=True, index=True)
    sync_strategy: Mapped[str] = mapped_column(String(50), default="snapshot")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sync_interval_seconds: Mapped[int] = mapped_column(Integer, default=300)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    snapshots: Mapped[list["DirectorySnapshot"]] = relationship(
        back_populates="tracked_directory", cascade="all, delete-orphan"
    )
    merkle_nodes: Mapped[list["MerkleNode"]] = relationship(
        foreign_keys="MerkleNode.tracked_directory_id", cascade="all, delete-orphan"
    )


class DirectorySnapshot(Base):
    """Stores file state for snapshot-based sync strategy"""
    __tablename__ = "directory_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    tracked_directory_id: Mapped[int] = mapped_column(ForeignKey("tracked_directories.id"), index=True)
    relative_path: Mapped[str] = mapped_column(String(1024))
    file_hash: Mapped[str] = mapped_column(String(64), index=True)
    file_size: Mapped[int] = mapped_column(Integer)
    modified_time: Mapped[float] = mapped_column(Float)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    tracked_directory: Mapped["TrackedDirectory"] = relationship(back_populates="snapshots")

    __table_args__ = (
        Index("idx_directory_snapshot_unique", "tracked_directory_id", "relative_path", unique=True),
    )


class MerkleNode(Base):
    """Stores Merkle tree nodes for merkle-based sync strategy"""
    __tablename__ = "merkle_nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    tracked_directory_id: Mapped[int] = mapped_column(ForeignKey("tracked_directories.id"), index=True)
    node_hash: Mapped[str] = mapped_column(String(64), index=True)
    node_type: Mapped[str] = mapped_column(String(10))
    relative_path: Mapped[str] = mapped_column(String(1024))
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("merkle_nodes.id"), nullable=True)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    tracked_directory: Mapped["TrackedDirectory"] = relationship(back_populates="merkle_nodes")
    children: Mapped[list["MerkleNode"]] = relationship(
        back_populates="parent",
        remote_side="MerkleNode.id"
    )
    parent: Mapped[Optional["MerkleNode"]] = relationship(
        back_populates="children",
        remote_side="MerkleNode.parent_id"
    )
