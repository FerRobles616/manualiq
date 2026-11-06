"""add heartbeat to ingestion jobs

Revision ID: f5c2d9b8a1e3
Revises: d8e4f1a2c6b7
Create Date: 2026-11-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f5c2d9b8a1e3"
down_revision: str | None = "d8e4f1a2c6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("ingestion_jobs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ingestion_jobs", schema=None) as batch_op:
        batch_op.drop_column("heartbeat_at")
