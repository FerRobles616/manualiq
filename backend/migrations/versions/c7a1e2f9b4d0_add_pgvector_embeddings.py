"""add pgvector embeddings and HNSW index

Revision ID: c7a1e2f9b4d0
Revises: 2ae9038f42fe
Create Date: 2026-11-06

The vector column is PostgreSQL-only. SQLite keeps the JSON embedding column and
performs cosine similarity in process; the migration is a no-op there.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c7a1e2f9b4d0"
down_revision: str | None = "2ae9038f42fe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 256


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(f"ALTER TABLE chunks ADD COLUMN embedding_vec vector({EMBEDDING_DIM})")
    op.execute(
        "UPDATE chunks "
        "SET embedding_vec = CAST(embedding::text AS vector) "
        "WHERE embedding_vec IS NULL"
    )
    op.execute(
        "CREATE INDEX ix_chunks_embedding_vec_hnsw "
        "ON chunks USING hnsw (embedding_vec vector_cosine_ops)"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_vec_hnsw")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS embedding_vec")
