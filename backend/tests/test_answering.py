from sqlalchemy.orm import Session

from app.services.answering import ExtractiveAnswerService
from app.services.embeddings import HashEmbeddingProvider
from app.services.ingestion import ingest_pdf_bytes
from app.services.retrieval import RetrievalService
from tests.factories import make_pdf


def test_answer_is_grounded_in_a_citation(
    db_session: Session,
    provider: HashEmbeddingProvider,
    tmp_path,
) -> None:
    ingest_pdf_bytes(
        db_session,
        make_pdf(
            [
                (
                    "Hydraulic Press H-200 Service Manual. "
                    "The maximum operating pressure is 180 bar. "
                    "The hydraulic oil is ISO VG 46."
                ),
                ("Maintenance schedule. Change the oil every 500 operating hours."),
            ]
        ),
        filename="hydraulic_press_h200.pdf",
        provider=provider,
        upload_dir=str(tmp_path),
    )

    retrieved = RetrievalService(provider).retrieve(
        db_session,
        "What is the maximum operating pressure?",
    )
    result = ExtractiveAnswerService().answer(
        "What is the maximum operating pressure?",
        retrieved,
        min_similarity=0.20,
    )

    assert result.refused is False
    assert "180 bar" in result.answer
    assert "Service Manual" not in result.answer
    assert result.citations
    assert result.citations[0].page == 1
    assert "180 bar" in result.citations[0].quote
    assert result.confidence > 0.2


def test_answer_refuses_when_there_is_no_evidence(
    db_session: Session,
    provider: HashEmbeddingProvider,
    tmp_path,
) -> None:
    ingest_pdf_bytes(
        db_session,
        make_pdf(["The maximum operating pressure is 180 bar."]),
        filename="hydraulic.pdf",
        provider=provider,
        upload_dir=str(tmp_path),
    )

    retrieved = RetrievalService(provider).retrieve(
        db_session,
        "What is the warranty?",
    )
    result = ExtractiveAnswerService().answer(
        "What is the warranty?",
        retrieved,
        min_similarity=0.20,
    )

    assert result.refused is True
    assert result.citations == []
    assert "couldn't find enough evidence" in result.answer


def test_answer_refuses_without_retrieved_chunks() -> None:
    result = ExtractiveAnswerService().answer(
        "What is the warranty?",
        [],
    )

    assert result.refused is True
    assert result.confidence == 0.0
