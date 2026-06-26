from datetime import date, datetime

from pydantic import BaseModel, Field


class CertificateExtractionRead(BaseModel):
    id: str
    organization_id: str
    product_id: str | None
    file_name: str
    certification_name: str | None
    expiry_date: date | None
    emission_value: float | None
    compliance_information: str | None
    extracted_json: dict
    document_type: str | None
    extraction_method: str | None
    extraction_confidence: float | None
    field_confidence_json: dict | None
    evidence_json: dict | None
    review_notes: str | None
    reviewed_by_user_id: str | None
    reviewed_at: datetime | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CertificateExtractionList(BaseModel):
    items: list[CertificateExtractionRead]
    total: int


class CertificateExtractionUpdate(BaseModel):
    certification_name: str | None = Field(default=None, max_length=160)
    expiry_date: date | None = None
    emission_value: float | None = Field(default=None, ge=0)
    compliance_information: str | None = None
    document_type: str | None = Field(default=None, max_length=80)
    review_notes: str | None = None
    status: str | None = Field(default=None, pattern="^(needs_review|approved|rejected)$")
