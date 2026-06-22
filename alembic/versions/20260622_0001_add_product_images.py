"""add product image fields

Revision ID: 20260622_0001
Revises:
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260622_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("products", sa.Column("image_url", sa.String(length=600), nullable=True))
    op.add_column("products", sa.Column("image_key", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "image_key")
    op.drop_column("products", "image_url")
