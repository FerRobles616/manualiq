import uuid
from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

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
