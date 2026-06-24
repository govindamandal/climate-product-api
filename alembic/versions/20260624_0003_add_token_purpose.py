"""add token purpose

Revision ID: 20260624_0003
Revises: 20260624_0002
Create Date: 2026-06-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260624_0003"
down_revision: str | None = "20260624_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "password_reset_tokens",
        sa.Column("purpose", sa.String(length=40), nullable=False, server_default="password_reset"),
    )


def downgrade() -> None:
    op.drop_column("password_reset_tokens", "purpose")
