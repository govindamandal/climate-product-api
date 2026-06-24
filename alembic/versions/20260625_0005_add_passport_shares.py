"""add passport shares

Revision ID: 20260625_0005
Revises: 20260624_0004
Create Date: 2026-06-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260625_0005"
down_revision: str | None = "20260624_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "passport_shares",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("token", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(op.f("ix_passport_shares_created_by_user_id"), "passport_shares", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_passport_shares_organization_id"), "passport_shares", ["organization_id"], unique=False)
    op.create_index(op.f("ix_passport_shares_product_id"), "passport_shares", ["product_id"], unique=False)
    op.create_index(op.f("ix_passport_shares_token"), "passport_shares", ["token"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_passport_shares_token"), table_name="passport_shares")
    op.drop_index(op.f("ix_passport_shares_product_id"), table_name="passport_shares")
    op.drop_index(op.f("ix_passport_shares_organization_id"), table_name="passport_shares")
    op.drop_index(op.f("ix_passport_shares_created_by_user_id"), table_name="passport_shares")
    op.drop_table("passport_shares")
