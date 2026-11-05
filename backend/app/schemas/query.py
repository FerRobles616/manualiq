import uuid

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    document_ids: list[uuid.UUID] | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)


class CitationRead(BaseModel):
    document_id: uuid.UUID
    document_title: str
    page: int
    chunk_id: uuid.UUID
    quote: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationRead]
    refused: bool
    confidence: float
