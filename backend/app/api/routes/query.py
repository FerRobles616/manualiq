import uuid
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.api.deps import DbSession, EmbeddingDep
from app.core.config import get_settings
from app.schemas.query import CitationRead, QueryRequest, QueryResponse
from app.services.answering import AnswerResult, ExtractiveAnswerService
from app.services.retrieval import RetrievalService
from app.web.templates import templates

router = APIRouter(tags=["query"])


def _answer(
    db: DbSession,
    provider: EmbeddingDep,
    question: str,
    *,
    document_ids: list[uuid.UUID] | None = None,
    top_k: int | None = None,
) -> AnswerResult:
    settings = get_settings()
    retrieved = RetrievalService(provider).retrieve(
        db,
        question,
        top_k=top_k or settings.top_k,
        document_ids=document_ids,
    )
    return ExtractiveAnswerService().answer(
        question,
        retrieved,
        min_similarity=settings.min_similarity,
    )


@router.post("/api/query", response_model=QueryResponse)
def query_api(
    payload: QueryRequest,
    db: DbSession,
    provider: EmbeddingDep,
) -> QueryResponse:
    result = _answer(
        db,
        provider,
        payload.question,
        document_ids=payload.document_ids,
        top_k=payload.top_k,
    )
    return QueryResponse(
        answer=result.answer,
        citations=[
            CitationRead(
                document_id=citation.document_id,
                document_title=citation.document_title,
                page=citation.page,
                chunk_id=citation.chunk_id,
                quote=citation.quote,
            )
            for citation in result.citations
        ],
        refused=result.refused,
        confidence=result.confidence,
    )


@router.post("/query", response_class=HTMLResponse)
def query_ui(
    request: Request,
    db: DbSession,
    provider: EmbeddingDep,
    question: Annotated[str, Form(min_length=2, max_length=500)],
) -> HTMLResponse:
    result = _answer(db, provider, question)
    return templates.TemplateResponse(
        request=request,
        name="_answer.html",
        context={"result": result, "question": question},
    )
