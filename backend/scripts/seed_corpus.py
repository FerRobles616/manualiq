from pathlib import Path

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.embeddings import get_embedding_provider
from app.services.ingestion import ingest_pdf_bytes

TITLES = {
    "hydraulic_press_h200": "Hydraulic Press H-200 Service Manual",
    "hvac_cx40": "HVAC CX-40 Service Manual",
    "loto_procedure": "Lockout Tagout Procedure",
    "forklift_fl30": "Forklift FL-30 Service Manual",
    "air_compressor_ac75": "Air Compressor AC-75 Service Manual",
    "confined_space_sop": "Confined Space Entry Procedure",
}


def main() -> None:
    settings = get_settings()
    provider = get_embedding_provider()
    corpus_dir = Path(settings.corpus_dir)
    documents = sorted(corpus_dir.glob("*.pdf"))

    if not documents:
        raise SystemExit(f"No PDFs found in {corpus_dir}")

    with SessionLocal() as db:
        for path in documents:
            document = ingest_pdf_bytes(
                db,
                path.read_bytes(),
                filename=path.name,
                title=TITLES.get(path.stem, path.stem),
                provider=provider,
            )
            print(
                f"{path.name}: {document.status.value} · "
                f"{document.page_count} pages · {len(document.chunks)} chunks"
            )


if __name__ == "__main__":
    main()
