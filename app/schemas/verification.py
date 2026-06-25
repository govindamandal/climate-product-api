from datetime import datetime

from pydantic import BaseModel, Field


class ProductVerificationCreate(BaseModel):
    product_id: str
    verification_type: str = Field(default="internal_review", max_length=80)
    scope: str = Field(default="product_dpp", max_length=120)
    evidence_summary: str = ""
    requester_notes: str = ""


class ProductVerificationReview(BaseModel):
    status: str = Field(pattern="^(approved|rejected)$")
    reviewer_notes: str = ""


class ProductVerificationRead(BaseModel):
    id: str
    organization_id: str
    product_id: str
    product_name: str
    product_category: str
    requested_by_user_id: str | None
    requested_by_email: str | None
    reviewed_by_user_id: str | None
    reviewed_by_email: str | None
    status: str
    verification_type: str
    scope: str
    evidence_summary: str
    requester_notes: str
    reviewer_notes: str
    submitted_at: datetime
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProductVerificationList(BaseModel):
    items: list[ProductVerificationRead]
    total: int
