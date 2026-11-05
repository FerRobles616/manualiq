from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.services.embeddings import HashEmbeddingProvider, get_embedding_provider
from tests.factories import make_pdf


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    testing_session = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    with testing_session() as session:
        yield session

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def provider() -> HashEmbeddingProvider:
    return HashEmbeddingProvider(256)


@pytest.fixture()
def client(
    db_session: Session,
    provider: HashEmbeddingProvider,
    tmp_path,
    monkeypatch,
) -> Generator[TestClient, None, None]:
    settings = get_settings()
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_embedding_provider] = lambda: provider
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def pdf_bytes() -> bytes:
    return make_pdf(
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
        ]
    )
