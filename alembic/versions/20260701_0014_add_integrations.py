"""add integrations

Revision ID: 20260701_0014
Revises: 20260626_0013
Create Date: 2026-07-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260701_0014"
down_revision: str | None = "20260626_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_connections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("connection_type", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("webhook_url", sa.String(length=600), nullable=True),
        sa.Column("secret_hash", sa.String(length=255), nullable=True),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("events_json", sa.JSON(), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("last_delivery_status", sa.String(length=40), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_integration_connections_connection_type"), "integration_connections", ["connection_type"])
    op.create_index(op.f("ix_integration_connections_created_by_user_id"), "integration_connections", ["created_by_user_id"])
    op.create_index(op.f("ix_integration_connections_organization_id"), "integration_connections", ["organization_id"])
    op.create_index(op.f("ix_integration_connections_provider"), "integration_connections", ["provider"])
    op.create_index(op.f("ix_integration_connections_status"), "integration_connections", ["status"])
    op.create_table(
        "integration_event_deliveries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("connection_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("request_payload_json", sa.JSON(), nullable=False),
        sa.Column("response_status_code", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["connection_id"], ["integration_connections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_integration_event_deliveries_connection_id"), "integration_event_deliveries", ["connection_id"])
    op.create_index(op.f("ix_integration_event_deliveries_event_type"), "integration_event_deliveries", ["event_type"])
    op.create_index(op.f("ix_integration_event_deliveries_organization_id"), "integration_event_deliveries", ["organization_id"])
    op.create_index(op.f("ix_integration_event_deliveries_status"), "integration_event_deliveries", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_integration_event_deliveries_status"), table_name="integration_event_deliveries")
    op.drop_index(op.f("ix_integration_event_deliveries_organization_id"), table_name="integration_event_deliveries")
    op.drop_index(op.f("ix_integration_event_deliveries_event_type"), table_name="integration_event_deliveries")
    op.drop_index(op.f("ix_integration_event_deliveries_connection_id"), table_name="integration_event_deliveries")
    op.drop_table("integration_event_deliveries")
    op.drop_index(op.f("ix_integration_connections_status"), table_name="integration_connections")
    op.drop_index(op.f("ix_integration_connections_provider"), table_name="integration_connections")
    op.drop_index(op.f("ix_integration_connections_organization_id"), table_name="integration_connections")
    op.drop_index(op.f("ix_integration_connections_created_by_user_id"), table_name="integration_connections")
    op.drop_index(op.f("ix_integration_connections_connection_type"), table_name="integration_connections")
    op.drop_table("integration_connections")
