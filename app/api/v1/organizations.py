from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import CurrentUser, DbSession, require_roles
from app.core.security import hash_password
from app.models.enums import AuditAction, UserRole
from app.models.user import User
from app.repositories.organizations import OrganizationRepository
from app.repositories.users import UserRepository
from app.schemas.organization import InviteUserRequest, OrganizationRead, TeamRead
from app.services.audit_service import AuditService

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
    AuditService(db).record(
        action=AuditAction.CREATE,
        entity_type="user_invite",
        organization_id=user.organization_id,
        actor_user_id=user.id,
        entity_id=invited.id,
    )
    db.commit()
    org = OrganizationRepository(db).get(user.organization_id)
    return TeamRead(organization=org, members=repo.members(user.organization_id))
