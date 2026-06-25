"""add domain product model

Revision ID: 20260625_0007
Revises: 20260625_0006
Create Date: 2026-06-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260625_0007"
down_revision: str | None = "20260625_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("products", sa.Column("product_code", sa.String(length=80), nullable=False, server_default=""))
    op.add_column("products", sa.Column("declared_unit", sa.String(length=80), nullable=False, server_default="1 unit"))
    op.add_column("products", sa.Column("functional_unit", sa.String(length=180), nullable=False, server_default=""))
    op.add_column("products", sa.Column("lifecycle_scope", sa.String(length=80), nullable=False, server_default="cradle-to-gate"))
    op.add_column("products", sa.Column("reference_service_life_years", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("manufacturing_site", sa.String(length=180), nullable=False, server_default=""))
    op.add_column("products", sa.Column("plant_code", sa.String(length=80), nullable=False, server_default=""))
    op.add_column("products", sa.Column("product_standard", sa.String(length=160), nullable=False, server_default=""))
    op.add_column("products", sa.Column("pcr", sa.String(length=180), nullable=False, server_default=""))
    op.add_column("products", sa.Column("geography", sa.String(length=120), nullable=False, server_default=""))
    op.add_column("products", sa.Column("data_quality", sa.String(length=40), nullable=False, server_default="estimated"))
    op.add_column("products", sa.Column("technical_properties", sa.JSON(), nullable=False, server_default="{}"))

    op.create_table(
        "product_material_components",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("material_name", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("percentage", sa.Float(), nullable=False),
        sa.Column("recycled_content_pct", sa.Float(), nullable=False),
        sa.Column("bio_based_content_pct", sa.Float(), nullable=False),
        sa.Column("supplier", sa.String(length=160), nullable=False),
        sa.Column("origin_country", sa.String(length=80), nullable=False),
        sa.Column("evidence_reference", sa.String(length=240), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_product_material_components_organization_id"),
        "product_material_components",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_material_components_product_id"),
        "product_material_components",
        ["product_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_product_material_components_product_id"), table_name="product_material_components")
    op.drop_index(op.f("ix_product_material_components_organization_id"), table_name="product_material_components")
    op.drop_table("product_material_components")
    op.drop_column("products", "technical_properties")
    op.drop_column("products", "data_quality")
    op.drop_column("products", "geography")
    op.drop_column("products", "pcr")
    op.drop_column("products", "product_standard")
    op.drop_column("products", "plant_code")
    op.drop_column("products", "manufacturing_site")
    op.drop_column("products", "reference_service_life_years")
    op.drop_column("products", "lifecycle_scope")
    op.drop_column("products", "functional_unit")
    op.drop_column("products", "declared_unit")
    op.drop_column("products", "product_code")
