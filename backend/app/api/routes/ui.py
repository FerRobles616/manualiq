from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, EmbeddingDep
from app.core.config import get_settings
from app.models.document import Document
from app.services.answering import ExtractiveAnswerService
from app.services.ingestion import IngestionError, ingest_pdf_bytes, queue_pdf_bytes
from app.services.retrieval import RetrievalService
from app.web.templates import templates

router = APIRouter(tags=["ui"])


def _documents(db: DbSession) -> list[Document]:
    return list(
        db.scalars(
            select(Document)
            .options(selectinload(Document.chunks))
            .order_by(Document.created_at.desc())
        ).all()
    )


@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    db: DbSession,
    provider: EmbeddingDep,
    q: Annotated[str | None, Query(max_length=500)] = None,
) -> HTMLResponse:
    result = None
    if q and q.strip():
        settings = get_settings()
        retrieved = RetrievalService(provider).retrieve(
            db,
            q,
            top_k=settings.top_k,
        )
        result = ExtractiveAnswerService().answer(
            q,
            retrieved,
            min_similarity=settings.min_similarity,
        )

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "documents": _documents(db),
            "result": result,
            "question": q or "",
        },
    )


@router.get("/documents", response_class=HTMLResponse)
def documents_partial(request: Request, db: DbSession) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="_documents.html",
        context={"documents": _documents(db)},
    )


@router.post("/documents", response_class=HTMLResponse)
async def upload_document(
    request: Request,
    db: DbSession,
    provider: EmbeddingDep,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form()] = None,
) -> Response:
    settings = get_settings()
    filename = file.filename or "manual.pdf"
    data = await file.read(settings.max_upload_bytes + 1)
    error: str | None = None

    if len(data) > settings.max_upload_bytes:
        error = "The PDF exceeds the upload size limit."
    elif not data:
        error = "The uploaded file is empty."
    else:
        try:
            if settings.ingestion_mode == "queued":
                queue_pdf_bytes(
                    db,
                    data,
                    filename=filename,
                    title=title.strip() if title and title.strip() else None,
                )
            else:
                ingest_pdf_bytes(
                    db,
                    data,
                    filename=filename,
                    title=title.strip() if title and title.strip() else None,
                    provider=provider,
                )
        except IngestionError as exc:
            error = str(exc)

    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(
            request=request,
            name="_documents.html",
            context={"documents": _documents(db), "error": error},
        )

    return RedirectResponse("/", status_code=303)
