"""add document intelligence review

Revision ID: 20260626_0012
Revises: 20260626_0011
Create Date: 2026-06-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0012"
down_revision: str | None = "20260626_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("certificate_extractions", sa.Column("document_type", sa.String(length=80), nullable=True))
    op.add_column("certificate_extractions", sa.Column("extraction_method", sa.String(length=80), nullable=True))
    op.add_column("certificate_extractions", sa.Column("extraction_confidence", sa.Float(), nullable=True))
    op.add_column("certificate_extractions", sa.Column("field_confidence_json", sa.JSON(), nullable=True))
    op.add_column("certificate_extractions", sa.Column("evidence_json", sa.JSON(), nullable=True))
    op.add_column("certificate_extractions", sa.Column("review_notes", sa.Text(), nullable=True))
    op.add_column("certificate_extractions", sa.Column("reviewed_by_user_id", sa.String(length=36), nullable=True))
    op.add_column("certificate_extractions", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
    op.create_foreign_key(
        "fk_certificate_extractions_reviewed_by_user_id_users",
        "certificate_extractions",
        "users",
        ["reviewed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_certificate_extractions_reviewed_by_user_id"),
        "certificate_extractions",
        ["reviewed_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_certificate_extractions_reviewed_by_user_id"), table_name="certificate_extractions")
    op.drop_constraint(
        "fk_certificate_extractions_reviewed_by_user_id_users",
        "certificate_extractions",
        type_="foreignkey",
    )
    op.drop_column("certificate_extractions", "reviewed_at")
    op.drop_column("certificate_extractions", "reviewed_by_user_id")
    op.drop_column("certificate_extractions", "review_notes")
    op.drop_column("certificate_extractions", "evidence_json")
    op.drop_column("certificate_extractions", "field_confidence_json")
    op.drop_column("certificate_extractions", "extraction_confidence")
    op.drop_column("certificate_extractions", "extraction_method")
    op.drop_column("certificate_extractions", "document_type")
