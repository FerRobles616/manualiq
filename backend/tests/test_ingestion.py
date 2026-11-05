from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus
from app.services.embeddings import HashEmbeddingProvider
from app.services.ingestion import IngestionError, ingest_pdf_bytes
from tests.factories import make_pdf


def test_ingests_pdf_into_pages_and_chunks(
    db_session: Session,
    provider: HashEmbeddingProvider,
    tmp_path,
    pdf_bytes: bytes,
) -> None:
    document = ingest_pdf_bytes(
        db_session,
        pdf_bytes,
        filename="hydraulic_press_h200.pdf",
        provider=provider,
        upload_dir=str(tmp_path),
    )

    assert document.status == DocumentStatus.READY
    assert document.title == "hydraulic_press_h200"
    assert document.page_count == 2
    assert len(document.chunks) >= 2
    assert document.chunks[0].page == 1
    assert len(document.chunks[0].embedding) == 256
    assert document.chunks[0].token_count > 0


def test_duplicate_upload_returns_the_existing_document(
    db_session: Session,
    provider: HashEmbeddingProvider,
    tmp_path,
    pdf_bytes: bytes,
) -> None:
    first = ingest_pdf_bytes(
        db_session,
        pdf_bytes,
        filename="manual.pdf",
        provider=provider,
        upload_dir=str(tmp_path),
    )
    second = ingest_pdf_bytes(
        db_session,
        pdf_bytes,
        filename="manual-copy.pdf",
        provider=provider,
        upload_dir=str(tmp_path),
    )

    assert first.id == second.id


def test_rejects_non_pdf_bytes(
    db_session: Session,
    provider: HashEmbeddingProvider,
    tmp_path,
) -> None:
    try:
        ingest_pdf_bytes(
            db_session,
            b"not a pdf",
            filename="fake.pdf",
            provider=provider,
            upload_dir=str(tmp_path),
        )
    except IngestionError as error:
        assert "not a PDF" in str(error)
    else:
        raise AssertionError("Expected IngestionError")


def test_marks_document_failed_when_there_is_no_text(
    db_session: Session,
    provider: HashEmbeddingProvider,
    tmp_path,
) -> None:
    pdf = make_pdf([""])

    try:
        ingest_pdf_bytes(
            db_session,
            pdf,
            filename="empty.pdf",
            provider=provider,
            upload_dir=str(tmp_path),
        )
    except IngestionError as error:
        assert "No extractable text" in str(error)
    else:
        raise AssertionError("Expected IngestionError")

    failed = db_session.scalar(select(Document).where(Document.filename == "empty.pdf"))
    assert failed is not None
    assert failed.status == DocumentStatus.FAILED
    assert failed.error
