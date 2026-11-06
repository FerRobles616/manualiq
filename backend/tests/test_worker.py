from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import (
    Document,
    DocumentStatus,
    IngestionJob,
    IngestionJobStatus,
)
from app.services.embeddings import HashEmbeddingProvider
from app.services.ingestion import queue_pdf_bytes
from app.worker import claim_next_job, process_next_job, recover_stale_jobs
from tests.factories import make_pdf


def test_queued_pdf_is_processed_by_the_worker(
    db_session: Session,
    provider: HashEmbeddingProvider,
    tmp_path,
    pdf_bytes: bytes,
) -> None:
    document = queue_pdf_bytes(
        db_session,
        pdf_bytes,
        filename="hydraulic_press_h200.pdf",
        upload_dir=str(tmp_path),
    )

    assert document.status == DocumentStatus.QUEUED
    job = db_session.scalar(select(IngestionJob))
    assert job is not None
    assert job.status == IngestionJobStatus.QUEUED

    assert process_next_job(db_session, provider=provider) is True

    db_session.refresh(document)
    db_session.refresh(job)
    assert document.status == DocumentStatus.READY
    assert document.page_count == 2
    assert len(document.chunks) >= 2
    assert job.status == IngestionJobStatus.READY
    assert job.attempts == 1
    assert job.started_at is not None
    assert job.finished_at is not None


def test_failed_job_retries_then_marks_the_document_failed(
    db_session: Session,
    provider: HashEmbeddingProvider,
    tmp_path,
) -> None:
    document = queue_pdf_bytes(
        db_session,
        make_pdf([""]),
        filename="empty.pdf",
        upload_dir=str(tmp_path),
    )
    job = db_session.scalar(select(IngestionJob))
    assert job is not None
    job.max_attempts = 2
    db_session.commit()

    assert process_next_job(db_session, provider=provider) is True
    db_session.refresh(document)
    db_session.refresh(job)
    assert job.status == IngestionJobStatus.QUEUED
    assert job.attempts == 1
    assert document.status == DocumentStatus.QUEUED

    assert process_next_job(db_session, provider=provider) is True
    db_session.refresh(document)
    db_session.refresh(job)
    assert job.status == IngestionJobStatus.FAILED
    assert job.attempts == 2
    assert job.error
    assert document.status == DocumentStatus.FAILED
    assert document.error


def test_queued_upload_returns_202_and_becomes_ready(
    client,
    db_session: Session,
    provider: HashEmbeddingProvider,
    pdf_bytes: bytes,
    monkeypatch,
) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "ingestion_mode", "queued")

    upload = client.post(
        "/api/documents",
        files={
            "file": (
                "hydraulic_press_h200.pdf",
                pdf_bytes,
                "application/pdf",
            )
        },
        data={"title": "Hydraulic Press H-200"},
    )

    assert upload.status_code == 202, upload.text
    assert upload.json()["status"] == "queued"

    assert process_next_job(db_session, provider=provider) is True

    documents = client.get("/api/documents").json()
    assert documents[0]["status"] == "ready"
    assert documents[0]["chunk_count"] >= 2

    queued_document = db_session.scalar(select(Document))
    assert queued_document is not None
    assert queued_document.status == DocumentStatus.READY


def test_stale_processing_job_is_requeued(
    db_session: Session,
    provider: HashEmbeddingProvider,
    tmp_path,
    pdf_bytes: bytes,
) -> None:
    document = queue_pdf_bytes(
        db_session,
        pdf_bytes,
        filename="hydraulic_press_h200.pdf",
        upload_dir=str(tmp_path),
    )
    job = claim_next_job(db_session)
    assert job is not None
    assert job.status == IngestionJobStatus.PROCESSING
    assert job.heartbeat_at is not None

    job.heartbeat_at = datetime.now(UTC) - timedelta(seconds=120)
    db_session.commit()

    assert recover_stale_jobs(db_session, stale_seconds=10) == 1
    db_session.refresh(job)
    db_session.refresh(document)
    assert job.status == IngestionJobStatus.QUEUED
    assert job.heartbeat_at is None
    assert document.status == DocumentStatus.QUEUED

    assert process_next_job(db_session, provider=provider) is True
    db_session.refresh(document)
    assert document.status == DocumentStatus.READY
