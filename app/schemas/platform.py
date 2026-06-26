from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import SubscriptionStatus
from app.schemas.auth import UserRead
from app.schemas.organization import AuditLogRead, OrganizationRead


class PlatformOrganizationRead(OrganizationRead):
    user_count: int
    product_count: int
    billing_plan_key: str | None = None
    billing_plan_name: str | None = None
    billing_cycle: str | None = None
    billing_status: str | None = None


class PlatformOrganizationList(BaseModel):
    items: list[PlatformOrganizationRead]
    total: int


class PlatformOrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9-]+$")
    country: str = Field(default="Germany", min_length=2, max_length=80)
    admin_email: EmailStr
    admin_full_name: str = Field(min_length=2, max_length=160)


class PlatformOrganizationUpdate(BaseModel):
    subscription_status: SubscriptionStatus


class PlatformAnalytics(BaseModel):
    organization_count: int
    active_subscription_count: int
    user_count: int
    product_count: int
    audit_log_count: int


class PlatformUserList(BaseModel):
    items: list[UserRead]
    total: int


class PlatformAuditLogList(BaseModel):
    items: list[AuditLogRead]
    total: int


class PlatformOrganizationCreated(BaseModel):
    organization: PlatformOrganizationRead
    admin: UserRead
    temporary_password: str
    created_at: datetime
