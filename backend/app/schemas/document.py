import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentStatus


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    filename: str
    page_count: int
    status: DocumentStatus
    error: str | None
    created_at: datetime
    processed_at: datetime | None
    chunk_count: int = 0
