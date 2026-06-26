from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import Date, DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CertificateExtraction(Base):
    __tablename__ = "certificate_extractions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    certification_name: Mapped[str | None] = mapped_column(String(160))
    expiry_date: Mapped[date | None] = mapped_column(Date)
    emission_value: Mapped[float | None] = mapped_column(Float)
    compliance_information: Mapped[str | None] = mapped_column(Text)
    extracted_json: Mapped[dict] = mapped_column(JSON, default=dict)
    document_type: Mapped[str | None] = mapped_column(String(80))
    extraction_method: Mapped[str | None] = mapped_column(String(80))
    extraction_confidence: Mapped[float | None] = mapped_column(Float)
    field_confidence_json: Mapped[dict | None] = mapped_column(JSON)
    evidence_json: Mapped[dict | None] = mapped_column(JSON)
    review_notes: Mapped[str | None] = mapped_column(Text)
    reviewed_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(40), default="needs_review")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
