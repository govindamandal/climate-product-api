"""add professional report packs

Revision ID: 20260626_0013
Revises: 20260626_0012
Create Date: 2026-06-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0013"
down_revision: str | None = "20260626_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "professional_report_packs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("report_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("product_name", sa.String(length=180), nullable=False),
        sa.Column("readiness_score", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("sections_json", sa.JSON(), nullable=False),
        sa.Column("checks_json", sa.JSON(), nullable=False),
        sa.Column("report_json", sa.JSON(), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_professional_report_packs_created_by_user_id"), "professional_report_packs", ["created_by_user_id"])
    op.create_index(op.f("ix_professional_report_packs_organization_id"), "professional_report_packs", ["organization_id"])
    op.create_index(op.f("ix_professional_report_packs_product_id"), "professional_report_packs", ["product_id"])
    op.create_index(op.f("ix_professional_report_packs_report_type"), "professional_report_packs", ["report_type"])
    op.create_index(op.f("ix_professional_report_packs_status"), "professional_report_packs", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_professional_report_packs_status"), table_name="professional_report_packs")
    op.drop_index(op.f("ix_professional_report_packs_report_type"), table_name="professional_report_packs")
    op.drop_index(op.f("ix_professional_report_packs_product_id"), table_name="professional_report_packs")
    op.drop_index(op.f("ix_professional_report_packs_organization_id"), table_name="professional_report_packs")
    op.drop_index(op.f("ix_professional_report_packs_created_by_user_id"), table_name="professional_report_packs")
    op.drop_table("professional_report_packs")
