"""add privacy controls

Revision ID: 20260626_0009
Revises: 20260626_0008
Create Date: 2026-06-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0009"
down_revision: str | None = "20260626_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization_privacy_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("data_region", sa.String(length=80), nullable=False),
        sa.Column("retention_period_days", sa.Integer(), nullable=False),
        sa.Column("allow_ai_processing", sa.Boolean(), nullable=False),
        sa.Column("allow_public_passport_sharing", sa.Boolean(), nullable=False),
        sa.Column("require_verification_for_exports", sa.Boolean(), nullable=False),
        sa.Column("data_processing_contact_email", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id"),
    )
    op.create_index(
        op.f("ix_organization_privacy_settings_organization_id"),
        "organization_privacy_settings",
        ["organization_id"],
    )
    op.create_table(
        "data_governance_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("requested_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("reviewed_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("request_type", sa.String(length=40), nullable=False),
        sa.Column("subject_type", sa.String(length=40), nullable=False),
        sa.Column("subject_id", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("resolution_notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_data_governance_requests_organization_id"), "data_governance_requests", ["organization_id"])
    op.create_index(op.f("ix_data_governance_requests_requested_by_user_id"), "data_governance_requests", ["requested_by_user_id"])
    op.create_index(op.f("ix_data_governance_requests_request_type"), "data_governance_requests", ["request_type"])
    op.create_index(op.f("ix_data_governance_requests_reviewed_by_user_id"), "data_governance_requests", ["reviewed_by_user_id"])
    op.create_index(op.f("ix_data_governance_requests_status"), "data_governance_requests", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_data_governance_requests_status"), table_name="data_governance_requests")
    op.drop_index(op.f("ix_data_governance_requests_reviewed_by_user_id"), table_name="data_governance_requests")
    op.drop_index(op.f("ix_data_governance_requests_request_type"), table_name="data_governance_requests")
    op.drop_index(op.f("ix_data_governance_requests_requested_by_user_id"), table_name="data_governance_requests")
    op.drop_index(op.f("ix_data_governance_requests_organization_id"), table_name="data_governance_requests")
    op.drop_table("data_governance_requests")
    op.drop_index(op.f("ix_organization_privacy_settings_organization_id"), table_name="organization_privacy_settings")
    op.drop_table("organization_privacy_settings")
