"""add lca calculations

Revision ID: 20260625_0006
Revises: 20260625_0005
Create Date: 2026-06-25
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20260625_0006"
down_revision: str | None = "20260625_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "emission_factors",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("lifecycle_stage", sa.String(length=12), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("factor_kg_co2e", sa.Float(), nullable=False),
        sa.Column("geography", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=240), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_emission_factors_category"), "emission_factors", ["category"], unique=False)
    op.create_index(op.f("ix_emission_factors_lifecycle_stage"), "emission_factors", ["lifecycle_stage"], unique=False)
    op.create_index(op.f("ix_emission_factors_name"), "emission_factors", ["name"], unique=False)
    op.create_index(op.f("ix_emission_factors_organization_id"), "emission_factors", ["organization_id"], unique=False)

    op.create_table(
        "lca_calculations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("declared_unit", sa.String(length=80), nullable=False),
        sa.Column("boundary", sa.String(length=80), nullable=False),
        sa.Column("method_version", sa.String(length=40), nullable=False),
        sa.Column("total_kg_co2e", sa.Float(), nullable=False),
        sa.Column("confidence", sa.String(length=40), nullable=False),
        sa.Column("inputs_json", sa.JSON(), nullable=False),
        sa.Column("stage_totals_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_lca_calculations_created_by_user_id"), "lca_calculations", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_lca_calculations_organization_id"), "lca_calculations", ["organization_id"], unique=False)
    op.create_index(op.f("ix_lca_calculations_product_id"), "lca_calculations", ["product_id"], unique=False)

    factors = [
        ("Portland cement clinker benchmark", "Cement", "A1-A3", "t", 850.0, "India", "Starter benchmark", "2026.1", "Use customer-verified factors for official EPD work."),
        ("Blended cement benchmark", "Cement", "A1-A3", "t", 620.0, "India", "Starter benchmark", "2026.1", "Representative lower-clinker cement benchmark."),
        ("Ready-mix concrete benchmark", "Concrete", "A1-A3", "m3", 320.0, "India", "Starter benchmark", "2026.1", "Representative cradle-to-gate concrete benchmark."),
        ("Electric arc furnace steel benchmark", "Steel", "A1-A3", "t", 780.0, "India", "Starter benchmark", "2026.1", "Representative recycled-route steel benchmark."),
        ("Blast furnace steel benchmark", "Steel", "A1-A3", "t", 2100.0, "India", "Starter benchmark", "2026.1", "Representative primary steel benchmark."),
        ("Road freight medium truck", "Transport", "A4", "t-km", 0.095, "India", "Starter benchmark", "2026.1", "Transport factor for tonne-kilometre estimates."),
        ("Grid electricity benchmark", "Energy", "A1-A3", "kWh", 0.72, "India", "Starter benchmark", "2026.1", "Replace with plant-specific electricity factor."),
        ("Natural gas heat benchmark", "Energy", "A1-A3", "kWh", 0.202, "India", "Starter benchmark", "2026.1", "Fuel combustion approximation."),
    ]
    created_at = datetime.utcnow()
    op.bulk_insert(
        sa.table(
            "emission_factors",
            sa.column("id", sa.String),
            sa.column("organization_id", sa.String),
            sa.column("name", sa.String),
            sa.column("category", sa.String),
            sa.column("lifecycle_stage", sa.String),
            sa.column("unit", sa.String),
            sa.column("factor_kg_co2e", sa.Float),
            sa.column("geography", sa.String),
            sa.column("source", sa.String),
            sa.column("version", sa.String),
            sa.column("notes", sa.Text),
            sa.column("created_at", sa.DateTime),
        ),
        [
            {
                "id": f"seed-factor-{index:02d}",
                "organization_id": None,
                "name": name,
                "category": category,
                "lifecycle_stage": stage,
                "unit": unit,
                "factor_kg_co2e": factor,
                "geography": geography,
                "source": source,
                "version": version,
                "notes": notes,
                "created_at": created_at,
            }
            for index, (name, category, stage, unit, factor, geography, source, version, notes) in enumerate(factors, start=1)
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_lca_calculations_product_id"), table_name="lca_calculations")
    op.drop_index(op.f("ix_lca_calculations_organization_id"), table_name="lca_calculations")
    op.drop_index(op.f("ix_lca_calculations_created_by_user_id"), table_name="lca_calculations")
    op.drop_table("lca_calculations")
    op.drop_index(op.f("ix_emission_factors_organization_id"), table_name="emission_factors")
    op.drop_index(op.f("ix_emission_factors_name"), table_name="emission_factors")
    op.drop_index(op.f("ix_emission_factors_lifecycle_stage"), table_name="emission_factors")
    op.drop_index(op.f("ix_emission_factors_category"), table_name="emission_factors")
    op.drop_table("emission_factors")
