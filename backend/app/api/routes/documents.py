import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, EmbeddingDep
from app.core.config import get_settings
from app.models.document import Document
from app.schemas.document import DocumentRead
from app.services.ingestion import IngestionError, ingest_pdf_bytes, queue_pdf_bytes

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _read(document: Document) -> DocumentRead:
    return DocumentRead(
        id=document.id,
        title=document.title,
        filename=document.filename,
        page_count=document.page_count,
        status=document.status,
        error=document.error,
        created_at=document.created_at,
        processed_at=document.processed_at,
        chunk_count=len(document.chunks),
    )


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    db: DbSession,
    provider: EmbeddingDep,
    response: Response,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form()] = None,
) -> DocumentRead:
    settings = get_settings()
    filename = file.filename or "manual.pdf"
    if file.content_type not in {
        "application/pdf",
        "application/octet-stream",
    } and not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload a PDF file.",
        )

    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="The PDF exceeds the upload size limit.",
        )
    if not data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The uploaded file is empty.",
        )

    try:
        if settings.ingestion_mode == "queued":
            document = queue_pdf_bytes(
                db,
                data,
                filename=filename,
                title=title.strip() if title and title.strip() else None,
            )
            response.status_code = status.HTTP_202_ACCEPTED
        else:
            document = ingest_pdf_bytes(
                db,
                data,
                filename=filename,
                title=title.strip() if title and title.strip() else None,
                provider=provider,
            )
    except IngestionError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    return _read(document)


@router.get("", response_model=list[DocumentRead])
def list_documents(db: DbSession) -> list[DocumentRead]:
    documents = db.scalars(
        select(Document).options(selectinload(Document.chunks)).order_by(Document.created_at.desc())
    ).all()
    return [_read(document) for document in documents]


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: uuid.UUID, db: DbSession) -> DocumentRead:
    document = db.scalar(
        select(Document).options(selectinload(Document.chunks)).where(Document.id == document_id)
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return _read(document)


@router.get("/{document_id}/file")
def download_document(document_id: uuid.UUID, db: DbSession) -> FileResponse:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    path = Path(document.storage_path)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored file not found",
        )
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=document.filename,
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: uuid.UUID, db: DbSession) -> Response:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    Path(document.storage_path).unlink(missing_ok=True)
    db.delete(document)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
