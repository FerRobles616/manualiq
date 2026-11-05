from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.embeddings import EmbeddingProvider, get_embedding_provider

DbSession = Annotated[Session, Depends(get_db)]
EmbeddingDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
