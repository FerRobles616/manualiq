import argparse
import time
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.document import (
    Document,
    DocumentStatus,
    IngestionJob,
    IngestionJobStatus,
)
from app.services.embeddings import EmbeddingProvider, get_embedding_provider
from app.services.ingestion import IngestionError, process_document_from_storage


def claim_next_job(db: Session) -> IngestionJob | None:
    """Claim one queued job. PostgreSQL uses SKIP LOCKED for multiple workers."""
    statement = (
        select(IngestionJob)
        .where(IngestionJob.status == IngestionJobStatus.QUEUED)
        .order_by(IngestionJob.created_at)
        .limit(1)
    )
    if db.get_bind().dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)

    job = db.scalar(statement)
    if job is None:
        return None

    job.status = IngestionJobStatus.PROCESSING
    job.attempts += 1
    job.started_at = datetime.now(UTC)
    job.error = None
    document = db.get(Document, job.document_id)
    if document is not None:
        document.status = DocumentStatus.PROCESSING
        document.error = None
    db.commit()
    db.refresh(job)
    return job


def process_next_job(
    db: Session,
    *,
    provider: EmbeddingProvider | None = None,
) -> bool:
    """Process at most one queued job. Returns True when a job was attempted."""
    job = claim_next_job(db)
    if job is None:
        return False

    provider = provider or get_embedding_provider()
    try:
        document = db.get(Document, job.document_id)
        if document is None:
            raise IngestionError("Document not found")
        process_document_from_storage(db, document, provider=provider)

        finished_job = db.get(IngestionJob, job.id)
        if finished_job is not None:
            finished_job.status = IngestionJobStatus.READY
            finished_job.error = None
            finished_job.finished_at = datetime.now(UTC)
            db.commit()
        return True
    except Exception as error:
        db.rollback()
        failed_job = db.get(IngestionJob, job.id)
        if failed_job is None:
            return True

        failed_job.error = str(error)
        document = db.get(Document, failed_job.document_id)
        if failed_job.attempts >= failed_job.max_attempts:
            failed_job.status = IngestionJobStatus.FAILED
            failed_job.finished_at = datetime.now(UTC)
            if document is not None:
                document.status = DocumentStatus.FAILED
                document.error = str(error)
        else:
            failed_job.status = IngestionJobStatus.QUEUED
            failed_job.finished_at = None
            if document is not None:
                document.status = DocumentStatus.QUEUED
                document.error = str(error)
        db.commit()
        print(f"ingestion job {failed_job.id} failed: {error}")
        return True


def run_worker(*, once: bool = False, poll_seconds: float | None = None) -> None:
    settings = get_settings()
    delay = poll_seconds if poll_seconds is not None else settings.worker_poll_seconds

    while True:
        with SessionLocal() as db:
            processed = process_next_job(db)
        if once:
            return
        if not processed:
            time.sleep(delay)


def main() -> None:
    parser = argparse.ArgumentParser(description="Process ManualIQ ingestion jobs.")
    parser.add_argument("--once", action="store_true", help="Process at most one job.")
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=None,
        help="Seconds to sleep when the queue is empty.",
    )
    args = parser.parse_args()
    run_worker(once=args.once, poll_seconds=args.poll_seconds)


if __name__ == "__main__":
    main()
