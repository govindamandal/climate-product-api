from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, require_roles
from app.core.security import hash_password
from app.models.audit import AuditLog
from app.models.enums import AuditAction, SubscriptionStatus, UserRole
from app.models.organization import Organization
from app.models.product import Product
from app.models.user import User
from app.repositories.organizations import OrganizationRepository
from app.repositories.users import UserRepository
from app.schemas.platform import (
    PlatformAnalytics,
    PlatformAuditLogList,
    PlatformOrganizationCreate,
    PlatformOrganizationCreated,
    PlatformOrganizationList,
    PlatformOrganizationRead,
    PlatformOrganizationUpdate,
    PlatformUserList,
)
from app.services.audit_service import AuditService

router = APIRouter(
    prefix="/platform",
    tags=["Super Admin Platform"],
    dependencies=[Depends(require_roles(UserRole.SUPER_ADMIN))],
)

TEMPORARY_ADMIN_PASSWORD = "ChangeMeNow!2026"


@router.get("/analytics", response_model=PlatformAnalytics)
def platform_analytics(db: DbSession) -> PlatformAnalytics:
    organization_count = int(db.scalar(select(func.count(Organization.id))) or 0)
    active_subscription_count = int(
        db.scalar(
            select(func.count(Organization.id)).where(
                Organization.subscription_status == SubscriptionStatus.ACTIVE
            )
        )
        or 0
    )
    return PlatformAnalytics(
        organization_count=organization_count,
        active_subscription_count=active_subscription_count,
        user_count=int(db.scalar(select(func.count(User.id))) or 0),
        product_count=int(db.scalar(select(func.count(Product.id))) or 0),
        audit_log_count=int(db.scalar(select(func.count(AuditLog.id))) or 0),
    )


@router.get("/organizations", response_model=PlatformOrganizationList)
def list_organizations(db: DbSession) -> PlatformOrganizationList:
    organizations = list(db.scalars(select(Organization).order_by(Organization.created_at.desc())))
    return PlatformOrganizationList(
        items=[_organization_read(db, organization) for organization in organizations],
        total=len(organizations),
    )


@router.post("/organizations", response_model=PlatformOrganizationCreated, status_code=201)
def create_organization(
    payload: PlatformOrganizationCreate, user: CurrentUser, db: DbSession
) -> PlatformOrganizationCreated:
    org_repo = OrganizationRepository(db)
    if org_repo.by_slug(payload.slug):
        raise HTTPException(status_code=409, detail="Organization slug is already in use")
    user_repo = UserRepository(db)
    if user_repo.by_email(payload.admin_email):
        raise HTTPException(status_code=409, detail="Admin email is already in use")
    organization = Organization(name=payload.name, slug=payload.slug, country=payload.country)
    db.add(organization)
    db.flush()
    admin = User(
        organization_id=organization.id,
        email=payload.admin_email,
        full_name=payload.admin_full_name,
        role=UserRole.ORG_ADMIN,
        hashed_password=hash_password(TEMPORARY_ADMIN_PASSWORD),
    )
    db.add(admin)
    db.flush()
    AuditService(db).record(
        action=AuditAction.CREATE,
        entity_type="organization",
        organization_id=organization.id,
        actor_user_id=user.id,
        entity_id=organization.id,
        metadata={"created_by": "super_admin", "admin_email": payload.admin_email},
    )
    db.commit()
    db.refresh(organization)
    db.refresh(admin)
    return PlatformOrganizationCreated(
        organization=_organization_read(db, organization),
        admin=admin,
        temporary_password=TEMPORARY_ADMIN_PASSWORD,
        created_at=datetime.utcnow(),
    )


@router.patch("/organizations/{organization_id}", response_model=PlatformOrganizationRead)
def update_organization_subscription(
    organization_id: str, payload: PlatformOrganizationUpdate, user: CurrentUser, db: DbSession
) -> PlatformOrganizationRead:
    organization = OrganizationRepository(db).get(organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    organization.subscription_status = payload.subscription_status
    AuditService(db).record(
        action=AuditAction.UPDATE,
        entity_type="subscription",
        organization_id=organization.id,
        actor_user_id=user.id,
        entity_id=organization.id,
        metadata={"subscription_status": payload.subscription_status.value},
    )
    db.commit()
    db.refresh(organization)
    return _organization_read(db, organization)


@router.get("/users", response_model=PlatformUserList)
def list_platform_users(db: DbSession) -> PlatformUserList:
    users = list(db.scalars(select(User).order_by(User.created_at.desc())))
    return PlatformUserList(items=users, total=len(users))


@router.get("/audit-logs", response_model=PlatformAuditLogList)
def list_platform_audit_logs(db: DbSession, limit: int = 50) -> PlatformAuditLogList:
    bounded_limit = max(1, min(limit, 200))
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(bounded_limit)
    total_stmt = select(func.count(AuditLog.id))
    return PlatformAuditLogList(
        items=list(db.scalars(stmt)),
        total=int(db.scalar(total_stmt) or 0),
    )


def _organization_read(db: DbSession, organization: Organization) -> PlatformOrganizationRead:
    user_count = int(db.scalar(select(func.count(User.id)).where(User.organization_id == organization.id)) or 0)
    product_count = int(
        db.scalar(select(func.count(Product.id)).where(Product.organization_id == organization.id)) or 0
    )
    return PlatformOrganizationRead(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        country=organization.country,
        subscription_status=organization.subscription_status,
        created_at=organization.created_at,
        user_count=user_count,
        product_count=product_count,
    )
