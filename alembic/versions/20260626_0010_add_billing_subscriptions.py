"""add billing subscriptions

Revision ID: 20260626_0010
Revises: 20260626_0009
Create Date: 2026-06-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260626_0010"
down_revision: str | None = "20260626_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "billing_subscriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("plan_key", sa.String(length=40), nullable=False),
        sa.Column("billing_cycle", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("seats_included", sa.Integer(), nullable=False),
        sa.Column("products_included", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_customer_id", sa.String(length=160), nullable=True),
        sa.Column("provider_subscription_id", sa.String(length=160), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(), nullable=False),
        sa.Column("current_period_ends_at", sa.DateTime(), nullable=False),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id"),
    )
    op.create_index(op.f("ix_billing_subscriptions_organization_id"), "billing_subscriptions", ["organization_id"])
    op.create_index(op.f("ix_billing_subscriptions_plan_key"), "billing_subscriptions", ["plan_key"])
    op.create_index(op.f("ix_billing_subscriptions_status"), "billing_subscriptions", ["status"])
    op.create_table(
        "billing_invoices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("subscription_id", sa.String(length=36), nullable=False),
        sa.Column("invoice_number", sa.String(length=80), nullable=False),
        sa.Column("amount_inr", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("invoice_url", sa.String(length=500), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subscription_id"], ["billing_subscriptions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_number"),
    )
    op.create_index(op.f("ix_billing_invoices_organization_id"), "billing_invoices", ["organization_id"])
    op.create_index(op.f("ix_billing_invoices_status"), "billing_invoices", ["status"])
    op.create_index(op.f("ix_billing_invoices_subscription_id"), "billing_invoices", ["subscription_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_billing_invoices_subscription_id"), table_name="billing_invoices")
    op.drop_index(op.f("ix_billing_invoices_status"), table_name="billing_invoices")
    op.drop_index(op.f("ix_billing_invoices_organization_id"), table_name="billing_invoices")
    op.drop_table("billing_invoices")
    op.drop_index(op.f("ix_billing_subscriptions_status"), table_name="billing_subscriptions")
    op.drop_index(op.f("ix_billing_subscriptions_plan_key"), table_name="billing_subscriptions")
    op.drop_index(op.f("ix_billing_subscriptions_organization_id"), table_name="billing_subscriptions")
    op.drop_table("billing_subscriptions")
