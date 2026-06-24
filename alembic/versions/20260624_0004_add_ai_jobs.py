"""add ai jobs

Revision ID: 20260624_0004
Revises: 20260624_0003
Create Date: 2026-06-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260624_0004"
down_revision: str | None = "20260624_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("job_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_jobs_job_type"), "ai_jobs", ["job_type"], unique=False)
    op.create_index(op.f("ix_ai_jobs_organization_id"), "ai_jobs", ["organization_id"], unique=False)
    op.create_index(op.f("ix_ai_jobs_product_id"), "ai_jobs", ["product_id"], unique=False)
    op.create_index(op.f("ix_ai_jobs_status"), "ai_jobs", ["status"], unique=False)
    op.create_index(op.f("ix_ai_jobs_user_id"), "ai_jobs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_jobs_user_id"), table_name="ai_jobs")
    op.drop_index(op.f("ix_ai_jobs_status"), table_name="ai_jobs")
    op.drop_index(op.f("ix_ai_jobs_product_id"), table_name="ai_jobs")
    op.drop_index(op.f("ix_ai_jobs_organization_id"), table_name="ai_jobs")
    op.drop_index(op.f("ix_ai_jobs_job_type"), table_name="ai_jobs")
    op.drop_table("ai_jobs")
