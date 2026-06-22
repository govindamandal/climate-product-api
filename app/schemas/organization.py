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


class TeamRead(BaseModel):
    organization: OrganizationRead
    members: list[UserRead]
