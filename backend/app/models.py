from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import UserDefinedType


class VectorBlob(UserDefinedType):
    """
    Custom type for storing vectors as raw bytes in libSQL.
    
    libsql_experimental doesn't support SQLAlchemy's Binary wrapper,
    so we use this custom type that handles bytes directly.
    """
    cache_ok = True
    
    def get_col_spec(self):
        return "BLOB"
    
    def bind_processor(self, dialect):
        # Return None to pass bytes through directly without any conversion
        return None
    
    def result_processor(self, dialect, coltype):
        # Return None to get bytes directly
        return None


class Base(DeclarativeBase):
    pass


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Vector stored as F32_BLOB for native libSQL vector search
    # Use float_list_to_f32_blob() to convert from list[float]
    vector: Mapped[bytes] = mapped_column(VectorBlob)
    model_name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    images: Mapped[List["Image"]] = relationship(back_populates="embedding")


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    file_path: Mapped[str] = mapped_column(String(1024))
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    embedding_id: Mapped[Optional[int]] = mapped_column(ForeignKey("embeddings.id"), nullable=True)

    # Embedding queue fields
    # Status values: "pending", "processing", "completed", "failed_retryable", "failed_permanent"
    embedding_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False, index=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    embedding: Mapped[Optional["Embedding"]] = relationship(back_populates="images")


class ClusteringRun(Base):
    __tablename__ = "clustering_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy: Mapped[str] = mapped_column(String(50), index=True)
    image_corpus_hash: Mapped[str] = mapped_column(String(64), index=True)
    parameters: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    assignments: Mapped[List["ClusterAssignment"]] = relationship(back_populates="clustering_run", cascade="all, delete-orphan")
    cluster_metadata_list: Mapped[List["ClusterMetadata"]] = relationship(back_populates="clustering_run", cascade="all, delete-orphan")


class ClusterAssignment(Base):
    __tablename__ = "cluster_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    clustering_run_id: Mapped[int] = mapped_column(ForeignKey("clustering_runs.id"), index=True)
    image_id: Mapped[int] = mapped_column(ForeignKey("images.id"), index=True)
    cluster_label: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # -1 for noise in HDBSCAN

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
