from sqlalchemy.orm import Session

from app.services.embeddings import HashEmbeddingProvider
from app.services.ingestion import ingest_pdf_bytes
from app.services.retrieval import RetrievalService
from tests.factories import make_pdf


def _ingest(
    db: Session,
    provider: HashEmbeddingProvider,
    tmp_path,
    pages: list[str],
    filename: str,
):
    return ingest_pdf_bytes(
        db,
        make_pdf(pages),
        filename=filename,
        provider=provider,
        upload_dir=str(tmp_path),
    )


def test_hybrid_retrieval_finds_the_right_page(
    db_session: Session,
    provider: HashEmbeddingProvider,
    tmp_path,
) -> None:
    _ingest(
        db_session,
        provider,
        tmp_path,
        [
            (
                "Hydraulic Press H-200 Service Manual. "
                "The maximum operating pressure is 180 bar. "
                "The hydraulic oil is ISO VG 46."
            ),
            (
                "Maintenance schedule. "
                "Change the oil every 500 operating hours. "
                "Inspect the hoses every 100 hours."
            ),
        ],
        "hydraulic_press_h200.pdf",
    )

    service = RetrievalService(provider)

    pressure = service.retrieve(
        db_session,
        "What is the maximum operating pressure?",
        top_k=3,
    )
    oil = service.retrieve(
        db_session,
        "When do I change the oil?",
        top_k=3,
    )

    assert pressure
    assert pressure[0].page == 1
    assert "180 bar" in pressure[0].content
    assert pressure[0].document_title == "hydraulic_press_h200"

    assert oil
    assert oil[0].page == 2
    assert "500 operating hours" in oil[0].content


def test_document_filter_restricts_results(
    db_session: Session,
    provider: HashEmbeddingProvider,
    tmp_path,
) -> None:
    hydraulic = _ingest(
        db_session,
        provider,
        tmp_path,
        [
            "The maximum operating pressure is 180 bar.",
        ],
        "hydraulic.pdf",
    )
    _ingest(
        db_session,
        provider,
        tmp_path,
        [
            "The warranty period is 24 months.",
        ],
        "warranty.pdf",
    )

    service = RetrievalService(provider)
    results = service.retrieve(
        db_session,
        "What is the maximum operating pressure?",
        top_k=5,
        document_ids=[hydraulic.id],
    )

    assert results
    assert all(result.document_id == hydraulic.id for result in results)
    assert (
        service.retrieve(
            db_session,
            "What is the warranty period?",
            top_k=5,
            document_ids=[hydraulic.id],
        )
        == []
    )
