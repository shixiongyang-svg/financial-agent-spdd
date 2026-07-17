from __future__ import annotations

import logging

from sqlalchemy import text

from ..core.database import SessionFactory, to_pgvector_literal
from ..core.logging import get_request_id
from ..models.retrieval import ComplaintRow, DocumentChunk
from .llm_service import LLMService

logger = logging.getLogger(__name__)


class RetrievalService:
    def __init__(self, session_factory: SessionFactory, llm: LLMService) -> None:
        self._session_factory = session_factory
        self._llm = llm

    async def retrieve_docs(
        self,
        query: str,
        *,
        limit: int = 5,
        request_id: str | None = None,
    ) -> list[DocumentChunk]:
        if limit <= 0:
            return []

        logger.info(
            "retrieve_docs_start",
            extra={"request_id": get_request_id() or request_id, "query": query, "limit": limit},
        )
        query_vector = await self._llm.embed(query, request_id=request_id)
        vector_literal = to_pgvector_literal(query_vector)

        sql = text(
            """
            SELECT
              d.id AS doc_id,
              d.source_file,
              d.chunk_index,
              d.content,
              1 - (de.embedding <=> CAST(:query_vector AS vector)) AS similarity
            FROM doc_embeddings AS de
            JOIN docs AS d ON d.id = de.doc_id
            ORDER BY de.embedding <=> CAST(:query_vector AS vector)
            LIMIT :limit
            """
        )
        with self._session_factory() as session:
            rows = session.execute(sql, {"query_vector": vector_literal, "limit": limit}).mappings().all()

        results = [DocumentChunk(**row) for row in rows]
        logger.info(
            "retrieve_docs_success",
            extra={"request_id": get_request_id() or request_id, "count": len(results)},
        )
        return results

    async def retrieve_complaints(
        self,
        query: str,
        *,
        limit: int = 10,
        product: str | None = None,
        request_id: str | None = None,
    ) -> list[ComplaintRow]:
        if limit <= 0:
            return []

        logger.info(
            "retrieve_complaints_start",
            extra={
                "request_id": get_request_id() or request_id,
                "query": query,
                "limit": limit,
                "product": product,
            },
        )
        product_pattern = f"%{product}%" if product else "%"
        params: dict[str, str | int | bool] = {
            "query_pattern": f"%{query}%",
            "product_pattern": product_pattern,
            "product_filter_enabled": bool(product),
            "limit": limit,
        }
        sql = text(
            """
            SELECT
              complaint_id,
              date_received,
              product,
              issue,
              company,
              state,
              submitted_via,
              narrative
            FROM complaints
            WHERE (:product_filter_enabled = FALSE OR product ILIKE :product_pattern)
              AND (
                issue ILIKE :query_pattern
                OR company ILIKE :query_pattern
                OR COALESCE(narrative, '') ILIKE :query_pattern
              )
            ORDER BY date_received DESC NULLS LAST, complaint_id DESC
            LIMIT :limit
            """
        )
        with self._session_factory() as session:
            rows = session.execute(sql, params).mappings().all()

        results = [ComplaintRow(**row) for row in rows]
        logger.info(
            "retrieve_complaints_success",
            extra={"request_id": get_request_id() or request_id, "count": len(results)},
        )
        return results
