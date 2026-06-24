from datetime import datetime

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
