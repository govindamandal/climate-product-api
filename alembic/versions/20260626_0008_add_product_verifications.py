"""add product verifications

Revision ID: 20260626_0008
Revises: 20260625_0007
Create Date: 2026-06-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0008"
down_revision: str | None = "20260625_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_verifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("requested_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("reviewed_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("verification_type", sa.String(length=80), nullable=False),
        sa.Column("scope", sa.String(length=120), nullable=False),
        sa.Column("evidence_summary", sa.Text(), nullable=False),
        sa.Column("requester_notes", sa.Text(), nullable=False),
        sa.Column("reviewer_notes", sa.Text(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_product_verifications_organization_id"), "product_verifications", ["organization_id"])
    op.create_index(op.f("ix_product_verifications_product_id"), "product_verifications", ["product_id"])
    op.create_index(op.f("ix_product_verifications_requested_by_user_id"), "product_verifications", ["requested_by_user_id"])
    op.create_index(op.f("ix_product_verifications_reviewed_by_user_id"), "product_verifications", ["reviewed_by_user_id"])
    op.create_index(op.f("ix_product_verifications_status"), "product_verifications", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_product_verifications_status"), table_name="product_verifications")
    op.drop_index(op.f("ix_product_verifications_reviewed_by_user_id"), table_name="product_verifications")
    op.drop_index(op.f("ix_product_verifications_requested_by_user_id"), table_name="product_verifications")
    op.drop_index(op.f("ix_product_verifications_product_id"), table_name="product_verifications")
    op.drop_index(op.f("ix_product_verifications_organization_id"), table_name="product_verifications")
    op.drop_table("product_verifications")
