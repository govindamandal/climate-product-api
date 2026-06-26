from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import CurrentUser, DbSession, require_roles
from app.core.security import hash_password
from app.models.enums import AuditAction, UserRole
from app.models.user import User
from app.repositories.organizations import OrganizationRepository
from app.repositories.users import UserRepository
from app.schemas.auth import UserRead
from app.schemas.organization import (
    AuditLogList,
    DataGovernanceRequestCreate,
    DataGovernanceRequestList,
    DataGovernanceRequestRead,
    DataGovernanceRequestReview,
    InviteUserRequest,
    OrganizationRead,
    OrganizationPrivacySettingsRead,
    OrganizationPrivacySettingsUpdate,
    TeamMemberUpdate,
    TeamRead,
)
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from app.services.privacy_service import PrivacyService

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get("/current", response_model=OrganizationRead)
def current_organization(user: CurrentUser, db: DbSession) -> OrganizationRead:
    if not user.organization_id:
        raise HTTPException(status_code=404, detail="No organization")
    org = OrganizationRepository(db).get(user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.get("/team", response_model=TeamRead)
def team(user: CurrentUser, db: DbSession) -> TeamRead:
    if not user.organization_id:
        raise HTTPException(status_code=404, detail="No organization")
    org = OrganizationRepository(db).get(user.organization_id)
    return TeamRead(organization=org, members=UserRepository(db).members(user.organization_id))


@router.get(
    "/audit-logs",
    response_model=AuditLogList,
    dependencies=[Depends(require_roles(UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN))],
)
def audit_logs(
    user: CurrentUser,
    db: DbSession,
    limit: int = 25,
    action: str | None = None,
    entity_type: str | None = None,
    search: str | None = None,
) -> AuditLogList:
    if not user.organization_id:
        raise HTTPException(status_code=404, detail="No organization")
    items, total = AuditService(db).list_logs(
        organization_id=user.organization_id,
        limit=limit,
        action=action,
        entity_type=entity_type,
        search=search,
    )
    return AuditLogList(items=items, total=total)


@router.get("/privacy-settings", response_model=OrganizationPrivacySettingsRead)
def privacy_settings(user: CurrentUser, db: DbSession) -> OrganizationPrivacySettingsRead:
    return PrivacyService(db).get_settings(user)


@router.patch(
    "/privacy-settings",
    response_model=OrganizationPrivacySettingsRead,
    dependencies=[Depends(require_roles(UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN))],
)
def update_privacy_settings(
    payload: OrganizationPrivacySettingsUpdate,
    user: CurrentUser,
    db: DbSession,
) -> OrganizationPrivacySettingsRead:
    return PrivacyService(db).update_settings(user, payload)


@router.get("/data-requests", response_model=DataGovernanceRequestList)
def data_requests(
    user: CurrentUser,
    db: DbSession,
    status: str | None = None,
    request_type: str | None = None,
) -> DataGovernanceRequestList:
    return PrivacyService(db).list_requests(user, status=status, request_type=request_type)


@router.post("/data-requests", response_model=DataGovernanceRequestRead, status_code=201)
def create_data_request(
    payload: DataGovernanceRequestCreate,
    user: CurrentUser,
    db: DbSession,
) -> DataGovernanceRequestRead:
    return PrivacyService(db).create_request(user, payload)


@router.patch(
    "/data-requests/{request_id}",
    response_model=DataGovernanceRequestRead,
    dependencies=[Depends(require_roles(UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN))],
)
def review_data_request(
    request_id: str,
    payload: DataGovernanceRequestReview,
    user: CurrentUser,
    db: DbSession,
) -> DataGovernanceRequestRead:
    return PrivacyService(db).review_request(user, request_id, payload)


@router.post(
    "/invites",
    response_model=TeamRead,
    dependencies=[Depends(require_roles(UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN))],
)
def invite_user(payload: InviteUserRequest, user: CurrentUser, db: DbSession) -> TeamRead:
    if not user.organization_id:
        raise HTTPException(status_code=400, detail="No organization")
    if payload.role == UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=400, detail="Cannot invite super admins")
    repo = UserRepository(db)
    if repo.by_email(payload.email, user.organization_id):
        raise HTTPException(status_code=409, detail="User already exists")
    invited = User(
        organization_id=user.organization_id,
        email=payload.email,
        full_name=payload.full_name,
        role=payload.role,
        hashed_password=hash_password("ChangeMeNow!2026"),
    )
    db.add(invited)
    db.flush()
    org = OrganizationRepository(db).get(user.organization_id)
    invite_url = AuthService(db).create_password_reset_url(invited, purpose="invite_accept")
    AuditService(db).record(
        action=AuditAction.CREATE,
        entity_type="user_invite",
        organization_id=user.organization_id,
        actor_user_id=user.id,
        entity_id=invited.id,
    )
    db.commit()
    EmailService().send_invite(
        to_email=invited.email,
        full_name=invited.full_name,
        organization_name=org.name,
        role=invited.role.value,
        invite_url=invite_url,
    )
    return TeamRead(organization=org, members=repo.members(user.organization_id))


@router.patch(
    "/team/{member_id}",
    response_model=UserRead,
    dependencies=[Depends(require_roles(UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN))],
)
def update_team_member(
    member_id: str, payload: TeamMemberUpdate, user: CurrentUser, db: DbSession
) -> UserRead:
    if not user.organization_id:
        raise HTTPException(status_code=400, detail="No organization")
    member = UserRepository(db).get(member_id)
    if not member or member.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Team member not found")
    if payload.role == UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=400, detail="Cannot assign super admin role")
    if member.id == user.id and payload.role is not None and payload.role != member.role:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    if member.id == user.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(member, field, value)
    AuditService(db).record(
        action=AuditAction.UPDATE,
        entity_type="team_member",
        organization_id=user.organization_id,
        actor_user_id=user.id,
        entity_id=member.id,
        metadata=payload.model_dump(exclude_unset=True, mode="json"),
    )
    db.commit()
    db.refresh(member)
    return member


@router.delete(
    "/team/{member_id}",
    status_code=204,
    dependencies=[Depends(require_roles(UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN))],
)
def remove_team_member(member_id: str, user: CurrentUser, db: DbSession) -> None:
    if not user.organization_id:
        raise HTTPException(status_code=400, detail="No organization")
    member = UserRepository(db).get(member_id)
    if not member or member.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Team member not found")
    if member.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot remove your own account")
    AuditService(db).record(
        action=AuditAction.DELETE,
        entity_type="team_member",
        organization_id=user.organization_id,
        actor_user_id=user.id,
        entity_id=member.id,
        metadata={"email": member.email},
    )
    db.delete(member)
    db.commit()
