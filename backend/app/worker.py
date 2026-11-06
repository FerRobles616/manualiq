import argparse
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
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

    now = datetime.now(UTC)
    job.status = IngestionJobStatus.PROCESSING
    job.attempts += 1
    job.started_at = now
    job.heartbeat_at = now
    job.error = None
    document = db.get(Document, job.document_id)
    if document is not None:
        document.status = DocumentStatus.PROCESSING
        document.error = None
    db.commit()
    db.refresh(job)
    return job


def recover_stale_jobs(
    db: Session,
    *,
    stale_seconds: int | None = None,
) -> int:
    """Requeue processing jobs whose worker heartbeat has expired."""
    settings = get_settings()
    stale_after = stale_seconds or settings.worker_stale_seconds
    cutoff = datetime.now(UTC) - timedelta(seconds=stale_after)
    statement = select(IngestionJob).where(
        IngestionJob.status == IngestionJobStatus.PROCESSING,
        or_(
            IngestionJob.heartbeat_at.is_(None),
            IngestionJob.heartbeat_at < cutoff,
        ),
    )
    if db.get_bind().dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)

    stale_jobs = list(db.scalars(statement).all())
    now = datetime.now(UTC)
    for job in stale_jobs:
        document = db.get(Document, job.document_id)
        job.error = "Worker heartbeat expired; job requeued."
        job.heartbeat_at = None
        job.finished_at = now
        if job.attempts >= job.max_attempts:
            job.status = IngestionJobStatus.FAILED
            if document is not None:
                document.status = DocumentStatus.FAILED
                document.error = job.error
        else:
            job.status = IngestionJobStatus.QUEUED
            job.finished_at = None
            if document is not None:
                document.status = DocumentStatus.QUEUED
                document.error = job.error

    if stale_jobs:
        db.commit()
    return len(stale_jobs)


def _heartbeat_loop(
    job_id: uuid.UUID,
    interval: float,
    stop: threading.Event,
) -> None:
    while not stop.wait(interval):
        try:
            with SessionLocal() as heartbeat_db:
                heartbeat_db.execute(
                    update(IngestionJob)
                    .where(
                        IngestionJob.id == job_id,
                        IngestionJob.status == IngestionJobStatus.PROCESSING,
                    )
                    .values(heartbeat_at=datetime.now(UTC))
                )
                heartbeat_db.commit()
        except Exception:
            # A heartbeat failure is not fatal; stale recovery handles the job.
            pass


def process_next_job(
    db: Session,
    *,
    provider: EmbeddingProvider | None = None,
) -> bool:
    """Process at most one queued job. Returns True when a job was attempted."""
    job = claim_next_job(db)
    if job is None:
        return False

    settings = get_settings()
    heartbeat_stop = threading.Event()
    heartbeat_interval = max(10.0, settings.worker_stale_seconds / 3)
    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(job.id, heartbeat_interval, heartbeat_stop),
        daemon=True,
    )
    heartbeat_thread.start()

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
            finished_job.heartbeat_at = None
            db.commit()
        return True
    except Exception as error:
        db.rollback()
        failed_job = db.get(IngestionJob, job.id)
        if failed_job is None:
            return True

        failed_job.error = str(error)
        failed_job.heartbeat_at = None
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
    finally:
        heartbeat_stop.set()
        heartbeat_thread.join(timeout=1)


def run_worker(*, once: bool = False, poll_seconds: float | None = None) -> None:
    settings = get_settings()
    delay = poll_seconds if poll_seconds is not None else settings.worker_poll_seconds

    while True:
        with SessionLocal() as db:
            recover_stale_jobs(db)
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
