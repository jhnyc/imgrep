from typing import List, Optional, Tuple, TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.sql import Image, ClusteringRun, ClusterAssignment
from ..schemas.search import SearchResult

if TYPE_CHECKING:
    from .vector_store import VectorStoreService


class SearchService:
    """Service for search-related business logic"""

    def __init__(self, session: AsyncSession, vector_store: "VectorStoreService"):
        self.session = session
        self.vector_store = vector_store

    async def search_by_vector(
        self,
        query_embedding: List[float],
        top_k: int,
        strategy: Optional[str] = None,
        projection_strategy: Optional[str] = None,
        overlap_strategy: Optional[str] = None,
    ) -> Tuple[List[SearchResult], int]:
        """
        Search by vector embedding.

        Args:
            query_embedding: Query vector embedding
            top_k: Number of results to return
            strategy: Optional clustering strategy for coordinates
            projection_strategy: Optional projection strategy for coordinates
            overlap_strategy: Optional overlap strategy for coordinates

        Returns:
            Tuple of (search results list, total count in vector store)
        """
        # Search in Chroma
        chroma_results = self.vector_store.search_by_vector(query_embedding, top_k)

        if not chroma_results["ids"] or not chroma_results["ids"][0]:
            return [], self.vector_store.count()

        image_ids = [int(id_) for id_ in chroma_results["ids"][0]]
        # Ensure we only take top_k even if Chroma or logic elsewhere allows more
        image_ids = image_ids[:top_k]

        similarities = [1.0 - float(dist) for dist in chroma_results["distances"][0]]
        similarities = similarities[:top_k]

        results = []
        # Get Image and ClusterAssignment in one go if strategies are provided
        query = select(Image).where(Image.id.in_(image_ids))

        # Mapping for image_id to index to maintain Chroma's order
        id_to_idx = {img_id: i for i, img_id in enumerate(image_ids)}

        # Execute image fetch
        img_result = await self.session.execute(query)
        images = {img.id: img for img in img_result.scalars().all()}

        # Get coordinates if strategies are provided
        coords = {}
        if strategy and projection_strategy and overlap_strategy:
            coord_query = (
                select(ClusterAssignment)
                .join(ClusteringRun)
                .where(
                    ClusterAssignment.image_id.in_(image_ids),
                    ClusteringRun.is_current == True,
                    ClusteringRun.strategy == strategy,
                    ClusteringRun.projection_strategy == projection_strategy,
                    ClusteringRun.overlap_strategy == overlap_strategy
                )
            )
            coord_result = await self.session.execute(coord_query)
            coords = {ca.image_id: (ca.x, ca.y) for ca in coord_result.scalars().all()}

        for img_id, similarity in zip(image_ids, similarities):
            img = images.get(img_id)
            if img:
                x, y = coords.get(img_id, (None, None))
                results.append(SearchResult(
                    image_id=img_id,
                    similarity=similarity,
                    thumbnail_url=f"/api/thumbnails/{img.thumbnail_path}" if img.thumbnail_path else "",
                    x=x,
                    y=y
                ))

        return results, self.vector_store.count()

    def get_total_count(self) -> int:
        """Get total number of embeddings in the vector store"""
        return self.vector_store.count()
