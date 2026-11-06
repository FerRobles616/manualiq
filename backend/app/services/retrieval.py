import uuid
from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi
from sqlalchemy import select, text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models.document import Chunk
from app.services.embeddings import EmbeddingProvider
from app.services.text import tokenize


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    page: int
    content: str
    vector_score: float
    bm25_score: float
    rrf_score: float


class RetrievalService:
    def __init__(self, provider: EmbeddingProvider) -> None:
        self.provider = provider

    def retrieve(
        self,
        db: Session,
        question: str,
        *,
        top_k: int = 5,
        document_ids: list[uuid.UUID] | None = None,
    ) -> list[RetrievedChunk]:
        if db.get_bind().dialect.name == "postgresql":
            return self._retrieve_postgres(
                db,
                question,
                top_k=top_k,
                document_ids=document_ids,
            )
        return self._retrieve_sqlite(
            db,
            question,
            top_k=top_k,
            document_ids=document_ids,
        )

    def _retrieve_sqlite(
        self,
        db: Session,
        question: str,
        *,
        top_k: int,
        document_ids: list[uuid.UUID] | None,
    ) -> list[RetrievedChunk]:
        query = select(Chunk).options(selectinload(Chunk.document))
        if document_ids:
            query = query.where(Chunk.document_id.in_(document_ids))

        chunks = list(db.scalars(query).all())
        if not chunks:
            return []

        query_vector = self.provider.embed([question])[0]
        query_norm = np.linalg.norm(query_vector)
        if query_norm == 0:
            return []
        query_vector = query_vector / query_norm

        matrix = np.asarray(
            [chunk.embedding for chunk in chunks],
            dtype=np.float32,
        )
        if matrix.ndim != 2 or matrix.shape[0] != len(chunks):
            return []

        row_norms = np.linalg.norm(matrix, axis=1)
        row_norms[row_norms == 0] = 1.0
        matrix = matrix / row_norms[:, None]
        vector_scores = matrix @ query_vector

        tokenized_chunks = [tokenize(chunk.content) for chunk in chunks]
        bm25 = BM25Okapi(tokenized_chunks)
        bm25_scores = np.asarray(
            bm25.get_scores(tokenize(question)),
            dtype=np.float32,
        )

        candidate_count = min(len(chunks), max(top_k * 10, 50))
        vector_order = [
            int(index) for index in np.argsort(-vector_scores) if float(vector_scores[index]) > 0
        ][:candidate_count]
        bm25_order = [
            int(index) for index in np.argsort(-bm25_scores) if float(bm25_scores[index]) > 0
        ][:candidate_count]

        if not vector_order and not bm25_order:
            return []

        rrf_scores: dict[int, float] = {}
        rank_constant = 60
        bm25_weight = 1.0 if bm25_order else 0.0
        vector_weight = 0.7 if bm25_order else 1.0

        for rank, index in enumerate(vector_order):
            rrf_scores[index] = rrf_scores.get(index, 0.0) + vector_weight / (
                rank_constant + rank + 1
            )
        if bm25_weight:
            for rank, index in enumerate(bm25_order):
                rrf_scores[index] = rrf_scores.get(index, 0.0) + bm25_weight / (
                    rank_constant + rank + 1
                )

        ordered = sorted(
            rrf_scores,
            key=lambda index: (
                -rrf_scores[index],
                -float(vector_scores[index]),
            ),
        )[:top_k]

        results: list[RetrievedChunk] = []
        for index in ordered:
            chunk = chunks[index]
            results.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    document_title=chunk.document.title,
                    page=chunk.page,
                    content=chunk.content,
                    vector_score=float(vector_scores[index]),
                    bm25_score=float(bm25_scores[index]),
                    rrf_score=float(rrf_scores[index]),
                )
            )
        return results

    def _retrieve_postgres(
        self,
        db: Session,
        question: str,
        *,
        top_k: int,
        document_ids: list[uuid.UUID] | None,
    ) -> list[RetrievedChunk]:
        settings = get_settings()
        query_vector = self.provider.embed([question])[0]
        query_vector_param = "[" + ",".join(f"{float(value):.9g}" for value in query_vector) + "]"
        candidate_count = max(top_k * 10, 50)

        filters = ""
        params: dict[str, object] = {
            "query_vector": query_vector_param,
            "question": question,
            "language": settings.fts_language,
            "limit": candidate_count,
        }
        if document_ids:
            filters = " AND c.document_id::text = ANY(:document_ids)"
            params["document_ids"] = [str(document_id) for document_id in document_ids]

        vector_sql = text(
            f"""
            SELECT
                c.id,
                c.document_id,
                d.title,
                c.page,
                c.content,
                1 - (c.embedding_vec <=> CAST(:query_vector AS vector)) AS vector_score
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.embedding_vec IS NOT NULL{filters}
            ORDER BY c.embedding_vec <=> CAST(:query_vector AS vector)
            LIMIT :limit
            """
        )
        lexical_sql = text(
            f"""
            SELECT
                c.id,
                c.document_id,
                d.title,
                c.page,
                c.content,
                ts_rank_cd(
                    to_tsvector(CAST(:language AS regconfig), c.content),
                    plainto_tsquery(CAST(:language AS regconfig), :question)
                ) AS bm25_score
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE to_tsvector(CAST(:language AS regconfig), c.content)
                  @@ plainto_tsquery(CAST(:language AS regconfig), :question){filters}
            ORDER BY bm25_score DESC
            LIMIT :limit
            """
        )

        vector_rows = list(db.execute(vector_sql, params).mappings())
        lexical_rows = list(db.execute(lexical_sql, params).mappings())
        if not vector_rows and not lexical_rows:
            return []

        chunks_by_id: dict[uuid.UUID, RowMapping] = {}
        vector_scores: dict[uuid.UUID, float] = {}
        bm25_scores: dict[uuid.UUID, float] = {}

        for row in vector_rows:
            chunk_id = row["id"]
            chunks_by_id.setdefault(chunk_id, row)
            vector_scores[chunk_id] = float(row["vector_score"])

        for row in lexical_rows:
            chunk_id = row["id"]
            chunks_by_id.setdefault(chunk_id, row)
            bm25_scores[chunk_id] = float(row["bm25_score"])

        vector_order = [row["id"] for row in vector_rows if float(row["vector_score"]) > 0]
        bm25_order = [row["id"] for row in lexical_rows if float(row["bm25_score"]) > 0]
        if not vector_order and not bm25_order:
            return []

        rrf_scores: dict[uuid.UUID, float] = {}
        rank_constant = 60
        bm25_weight = 1.0 if bm25_order else 0.0
        vector_weight = 0.7 if bm25_order else 1.0

        for rank, chunk_id in enumerate(vector_order):
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + vector_weight / (
                rank_constant + rank + 1
            )
        if bm25_weight:
            for rank, chunk_id in enumerate(bm25_order):
                rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + bm25_weight / (
                    rank_constant + rank + 1
                )

        ordered = sorted(
            rrf_scores,
            key=lambda chunk_id: (
                -rrf_scores[chunk_id],
                -vector_scores.get(chunk_id, 0.0),
            ),
        )[:top_k]

        results: list[RetrievedChunk] = []
        for chunk_id in ordered:
            row = chunks_by_id[chunk_id]
            results.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    document_id=row["document_id"],
                    document_title=row["title"],
                    page=int(row["page"]),
                    content=row["content"],
                    vector_score=vector_scores.get(chunk_id, 0.0),
                    bm25_score=bm25_scores.get(chunk_id, 0.0),
                    rrf_score=float(rrf_scores[chunk_id]),
                )
            )
        return results
