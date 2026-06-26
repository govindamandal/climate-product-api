from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import SubscriptionStatus, UserRole
from app.schemas.auth import UserRead


class OrganizationRead(BaseModel):
    id: str
    name: str
    slug: str
    country: str
    subscription_status: SubscriptionStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class InviteUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    role: UserRole = UserRole.ORG_USER


class TeamMemberUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    role: UserRole | None = None
    is_active: bool | None = None


class AuditLogRead(BaseModel):
    id: str
    organization_id: str | None
    actor_user_id: str | None
    action: str
    entity_type: str
    entity_id: str | None
    metadata_json: dict
    created_at: datetime
    actor_email: str | None = None
    actor_full_name: str | None = None
    organization_name: str | None = None
    description: str | None = None

    model_config = {"from_attributes": True}


class AuditLogList(BaseModel):
    items: list[AuditLogRead]
    total: int


class TeamRead(BaseModel):
    organization: OrganizationRead
    members: list[UserRead]


class OrganizationPrivacySettingsRead(BaseModel):
    id: str
    organization_id: str
    data_region: str
    retention_period_days: int
    allow_ai_processing: bool
    allow_public_passport_sharing: bool
    require_verification_for_exports: bool
    data_processing_contact_email: str | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrganizationPrivacySettingsUpdate(BaseModel):
    data_region: str | None = Field(default=None, min_length=2, max_length=80)
    retention_period_days: int | None = Field(default=None, ge=30, le=3650)
    allow_ai_processing: bool | None = None
    allow_public_passport_sharing: bool | None = None
    require_verification_for_exports: bool | None = None
    data_processing_contact_email: EmailStr | None = None


DataRequestType = Literal["export", "deletion", "correction"]
DataRequestSubject = Literal["organization", "product", "user", "certificate", "report"]
DataRequestStatus = Literal["open", "completed", "rejected"]


class DataGovernanceRequestCreate(BaseModel):
    request_type: DataRequestType
    subject_type: DataRequestSubject
    subject_id: str = Field(default="", max_length=120)
    reason: str = Field(default="", max_length=1200)


class DataGovernanceRequestReview(BaseModel):
    status: Literal["completed", "rejected"]
    resolution_notes: str = Field(default="", max_length=1200)


class DataGovernanceRequestRead(BaseModel):
    id: str
    organization_id: str
    requested_by_user_id: str | None
    requested_by_email: str | None = None
    reviewed_by_user_id: str | None
    reviewed_by_email: str | None = None
    request_type: DataRequestType
    subject_type: DataRequestSubject
    subject_id: str
    status: DataRequestStatus
    reason: str
    resolution_notes: str
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class DataGovernanceRequestList(BaseModel):
    items: list[DataGovernanceRequestRead]
    total: int
