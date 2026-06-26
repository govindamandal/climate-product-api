"""add ai safety metadata

Revision ID: 20260626_0011
Revises: 20260626_0010
Create Date: 2026-06-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0011"
down_revision: str | None = "20260626_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_jobs", sa.Column("provider", sa.String(length=40), nullable=True))
    op.add_column("ai_jobs", sa.Column("safety_status", sa.String(length=40), nullable=True))
    op.add_column("ai_jobs", sa.Column("safety_metadata_json", sa.JSON(), nullable=True))
    op.create_index(op.f("ix_ai_jobs_provider"), "ai_jobs", ["provider"])
    op.create_index(op.f("ix_ai_jobs_safety_status"), "ai_jobs", ["safety_status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_jobs_safety_status"), table_name="ai_jobs")
    op.drop_index(op.f("ix_ai_jobs_provider"), table_name="ai_jobs")
    op.drop_column("ai_jobs", "safety_metadata_json")
    op.drop_column("ai_jobs", "safety_status")
    op.drop_column("ai_jobs", "provider")
