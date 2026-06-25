from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(180), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    manufacturer: Mapped[str] = mapped_column(String(160), nullable=False)
    country: Mapped[str] = mapped_column(String(80), nullable=False)
    production_method: Mapped[str] = mapped_column(String(180), nullable=False)
    product_code: Mapped[str] = mapped_column(String(80), default="")
    declared_unit: Mapped[str] = mapped_column(String(80), default="1 unit")
    functional_unit: Mapped[str] = mapped_column(String(180), default="")
    lifecycle_scope: Mapped[str] = mapped_column(String(80), default="cradle-to-gate")
    reference_service_life_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    manufacturing_site: Mapped[str] = mapped_column(String(180), default="")
    plant_code: Mapped[str] = mapped_column(String(80), default="")
    product_standard: Mapped[str] = mapped_column(String(160), default="")
    pcr: Mapped[str] = mapped_column(String(180), default="")
    geography: Mapped[str] = mapped_column(String(120), default="")
    data_quality: Mapped[str] = mapped_column(String(40), default="estimated")
    technical_properties: Mapped[dict] = mapped_column(JSON, default=dict)
    image_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    image_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    material_composition: Mapped[dict] = mapped_column(JSON, default=dict)
    certifications: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    organization = relationship("Organization", back_populates="products")
    environmental_records = relationship(
        "EnvironmentalRecord",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="EnvironmentalRecord.recorded_at.desc()",
    )
    material_components = relationship(
        "ProductMaterialComponent",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductMaterialComponent.sort_order.asc()",
    )


class ProductMaterialComponent(Base):
    __tablename__ = "product_material_components"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    material_name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="")
    percentage: Mapped[float] = mapped_column(Float, nullable=False)
    recycled_content_pct: Mapped[float] = mapped_column(Float, default=0)
    bio_based_content_pct: Mapped[float] = mapped_column(Float, default=0)
    supplier: Mapped[str] = mapped_column(String(160), default="")
    origin_country: Mapped[str] = mapped_column(String(80), default="")
    evidence_reference: Mapped[str] = mapped_column(String(240), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    product = relationship("Product", back_populates="material_components")


class EnvironmentalRecord(Base):
    __tablename__ = "environmental_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(index=True, nullable=False)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    co2_kg: Mapped[float] = mapped_column(Float, nullable=False)
    water_liters: Mapped[float] = mapped_column(Float, nullable=False)
    energy_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    transportation_kg_co2: Mapped[float] = mapped_column(Float, nullable=False)
    recyclability_score: Mapped[int] = mapped_column(Integer, nullable=False)
    sustainability_score: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="environmental_records")
