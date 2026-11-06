import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pymupdf
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import (
    Chunk,
    Document,
    DocumentStatus,
    IngestionJob,
    IngestionJobStatus,
)
from app.services.embeddings import EmbeddingProvider, get_embedding_provider
from app.services.text import chunk_text, normalize_whitespace, tokenize


class IngestionError(Exception):
    pass


@dataclass
class PageText:
    page: int
    text: str


def extract_pages(data: bytes) -> tuple[list[PageText], int, dict[str, str]]:
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        pages: list[PageText] = []
        for index, page in enumerate(pdf):
            blocks = page.get_text("blocks", sort=True)
            block_texts = [
                re.sub(r"\s*\n\s*", " ", block[4]).strip()
                for block in blocks
                if len(block) > 4 and isinstance(block[4], str) and block[4].strip()
            ]
            text = normalize_whitespace("\n\n".join(block_texts))
            if text:
                pages.append(PageText(page=index + 1, text=text))

        metadata = {
            key: value for key, value in (pdf.metadata or {}).items() if isinstance(value, str)
        }
        return pages, pdf.page_count, metadata


def create_document_from_bytes(
    db: Session,
    data: bytes,
    *,
    filename: str,
    title: str | None = None,
    upload_dir: str | None = None,
) -> Document:
    """Validate and persist a PDF without extracting or embedding it."""
    settings = get_settings()
    upload_dir = upload_dir or settings.upload_dir
    content_hash = hashlib.sha256(data).hexdigest()

    if len(data) > settings.max_upload_bytes:
        raise IngestionError("The PDF exceeds the upload size limit")
    if not data.startswith(b"%PDF"):
        raise IngestionError("The uploaded file is not a PDF")

    storage_dir = Path(upload_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{content_hash}.pdf"
    if not storage_path.exists():
        storage_path.write_bytes(data)

    existing = db.scalar(select(Document).where(Document.content_hash == content_hash))
    if existing is not None:
        if not Path(existing.storage_path).exists():
            existing.storage_path = str(storage_path)
            db.commit()
        return existing

    document = Document(
        title=title or Path(filename).stem,
        filename=filename,
        content_hash=content_hash,
        storage_path=str(storage_path),
        status=DocumentStatus.QUEUED,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def process_document(
    db: Session,
    document: Document,
    data: bytes,
    *,
    provider: EmbeddingProvider | None = None,
) -> Document:
    """Extract, chunk and embed an already persisted document."""
    settings = get_settings()
    provider = provider or get_embedding_provider()

    try:
        pages, page_count, _metadata = extract_pages(data)
        if not pages:
            raise IngestionError("No extractable text found in the PDF")

        # A retried job must not append duplicate chunks.
        db.execute(delete(Chunk).where(Chunk.document_id == document.id))

        pending: list[tuple[int, int, str]] = []
        chunk_index = 0
        for page in pages:
            for content in chunk_text(
                page.text,
                max_chars=settings.chunk_size,
                overlap=settings.chunk_overlap,
            ):
                pending.append((page.page, chunk_index, content))
                chunk_index += 1

        if not pending:
            raise IngestionError("No chunks could be created from the PDF")

        created_chunks: list[Chunk] = []
        batch_size = 32
        for start in range(0, len(pending), batch_size):
            batch = pending[start : start + batch_size]
            vectors = provider.embed([content for _, _, content in batch])
            if vectors.shape[0] != len(batch):
                raise IngestionError("Embedding provider returned an invalid shape")

            for (page_number, index, content), vector in zip(batch, vectors, strict=True):
                chunk = Chunk(
                    document_id=document.id,
                    page=page_number,
                    chunk_index=index,
                    content=content,
                    token_count=len(tokenize(content)),
                    embedding=[float(value) for value in vector],
                )
                db.add(chunk)
                created_chunks.append(chunk)

        # PostgreSQL uses a native pgvector column for the HNSW index. SQLite
        # keeps the JSON embedding and performs cosine search in process.
        db.flush()
        if db.get_bind().dialect.name == "postgresql":
            for chunk in created_chunks:
                db.execute(
                    text(
                        "UPDATE chunks "
                        "SET embedding_vec = CAST(:embedding AS vector) "
                        "WHERE id = :chunk_id"
                    ),
                    {
                        "embedding": json.dumps(chunk.embedding),
                        "chunk_id": chunk.id,
                    },
                )

        document.page_count = page_count
        document.status = DocumentStatus.READY
        document.processed_at = datetime.now(UTC)
        document.error = None
        db.commit()
        db.refresh(document)
        return document
    except Exception as error:
        db.rollback()
        failed = db.get(Document, document.id)
        if failed is not None:
            failed.status = DocumentStatus.FAILED
            failed.error = str(error)
            db.commit()
        if isinstance(error, IngestionError):
            raise
        raise IngestionError(str(error)) from error


def process_document_from_storage(
    db: Session,
    document: Document,
    *,
    provider: EmbeddingProvider | None = None,
) -> Document:
    path = Path(document.storage_path)
    if not path.exists():
        raise IngestionError("Stored PDF not found")
    return process_document(db, document, path.read_bytes(), provider=provider)


def ingest_pdf_bytes(
    db: Session,
    data: bytes,
    *,
    filename: str,
    title: str | None = None,
    provider: EmbeddingProvider | None = None,
    upload_dir: str | None = None,
) -> Document:
    """Synchronous ingestion used by the seed script and the default demo mode."""
    document = create_document_from_bytes(
        db,
        data,
        filename=filename,
        title=title,
        upload_dir=upload_dir,
    )
    if document.status == DocumentStatus.READY:
        return document
    return process_document(db, document, data, provider=provider)


def queue_pdf_bytes(
    db: Session,
    data: bytes,
    *,
    filename: str,
    title: str | None = None,
    upload_dir: str | None = None,
) -> Document:
    """Persist a PDF and enqueue a durable job for a worker."""
    settings = get_settings()
    document = create_document_from_bytes(
        db,
        data,
        filename=filename,
        title=title,
        upload_dir=upload_dir,
    )
    if document.status == DocumentStatus.READY:
        return document

    if document.status == DocumentStatus.FAILED:
        document.status = DocumentStatus.QUEUED
        document.error = None

    active_job = db.scalar(
        select(IngestionJob).where(
            IngestionJob.document_id == document.id,
            IngestionJob.status.in_([IngestionJobStatus.QUEUED, IngestionJobStatus.PROCESSING]),
        )
    )
    if active_job is None:
        db.add(
            IngestionJob(
                document_id=document.id,
                status=IngestionJobStatus.QUEUED,
                max_attempts=settings.worker_max_attempts,
            )
        )
    db.commit()
    db.refresh(document)
    return document
