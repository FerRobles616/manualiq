"""add durable ingestion jobs

Revision ID: d8e4f1a2c6b7
Revises: c7a1e2f9b4d0
Create Date: 2026-11-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8e4f1a2c6b7"
down_revision: str | None = "c7a1e2f9b4d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "processing",
                "ready",
                "failed",
                name="ingestion_job_status",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ingestion_jobs", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_ingestion_jobs_document_id"),
            ["document_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_ingestion_jobs_status"),
            ["status"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("ingestion_jobs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ingestion_jobs_status"))
        batch_op.drop_index(batch_op.f("ix_ingestion_jobs_document_id"))

    op.drop_table("ingestion_jobs")
