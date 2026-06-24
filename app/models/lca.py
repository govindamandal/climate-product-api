from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EmissionFactor(Base):
    __tablename__ = "emission_factors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(180), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    lifecycle_stage: Mapped[str] = mapped_column(String(12), index=True, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    factor_kg_co2e: Mapped[float] = mapped_column(Float, nullable=False)
    geography: Mapped[str] = mapped_column(String(80), default="Global")
    source: Mapped[str] = mapped_column(String(240), default="Seed benchmark")
    version: Mapped[str] = mapped_column(String(40), default="2026.1")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LcaCalculation(Base):
    __tablename__ = "lca_calculations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    declared_unit: Mapped[str] = mapped_column(String(80), nullable=False)
    boundary: Mapped[str] = mapped_column(String(80), nullable=False)
    method_version: Mapped[str] = mapped_column(String(40), nullable=False)
    total_kg_co2e: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[str] = mapped_column(String(40), nullable=False)
    inputs_json: Mapped[list] = mapped_column(JSON, default=list)
    stage_totals_json: Mapped[dict] = mapped_column(JSON, default=dict)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
