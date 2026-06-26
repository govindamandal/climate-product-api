from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import AuditAction, UserRole
from app.models.organization import DataGovernanceRequest, OrganizationPrivacySettings
from app.models.user import User
from app.schemas.organization import (
    DataGovernanceRequestCreate,
    DataGovernanceRequestList,
    DataGovernanceRequestRead,
    DataGovernanceRequestReview,
    OrganizationPrivacySettingsRead,
    OrganizationPrivacySettingsUpdate,
)
from app.services.audit_service import AuditService


class PrivacyService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_settings(self, user: User) -> OrganizationPrivacySettingsRead:
        settings = self._settings_for_org(self._organization_id(user))
        self.db.commit()
        self.db.refresh(settings)
        return OrganizationPrivacySettingsRead.model_validate(settings)

    def update_settings(
        self, user: User, payload: OrganizationPrivacySettingsUpdate
    ) -> OrganizationPrivacySettingsRead:
        self._require_org_admin(user)
        organization_id = self._organization_id(user)
        settings = self._settings_for_org(organization_id)
        changes = payload.model_dump(exclude_unset=True, mode="json")
        for field, value in changes.items():
            setattr(settings, field, value)
        AuditService(self.db).record(
            action=AuditAction.UPDATE,
            entity_type="privacy_settings",
            organization_id=organization_id,
            actor_user_id=user.id,
            entity_id=settings.id,
            metadata=changes,
        )
        self.db.commit()
        self.db.refresh(settings)
        return OrganizationPrivacySettingsRead.model_validate(settings)

    def list_requests(
        self,
        user: User,
        *,
        status: str | None = None,
        request_type: str | None = None,
    ) -> DataGovernanceRequestList:
        organization_id = self._organization_id(user)
        filters = [DataGovernanceRequest.organization_id == organization_id]
        if status:
            filters.append(DataGovernanceRequest.status == status)
        if request_type:
            filters.append(DataGovernanceRequest.request_type == request_type)
        stmt = (
            select(DataGovernanceRequest, User)
            .outerjoin(User, DataGovernanceRequest.requested_by_user_id == User.id)
            .where(*filters)
            .order_by(DataGovernanceRequest.created_at.desc())
        )
        count_stmt = select(func.count(DataGovernanceRequest.id)).where(*filters)
        rows = self.db.execute(stmt).all()
        return DataGovernanceRequestList(
            items=[self._read_request(request, requester=requester) for request, requester in rows],
            total=int(self.db.scalar(count_stmt) or 0),
        )

    def create_request(
        self, user: User, payload: DataGovernanceRequestCreate
    ) -> DataGovernanceRequestRead:
        organization_id = self._organization_id(user)
        request = DataGovernanceRequest(
            organization_id=organization_id,
            requested_by_user_id=user.id,
            request_type=payload.request_type,
            subject_type=payload.subject_type,
            subject_id=payload.subject_id,
            reason=payload.reason,
        )
        self.db.add(request)
        self.db.flush()
        AuditService(self.db).record(
            action=AuditAction.CREATE,
            entity_type="data_governance_request",
            organization_id=organization_id,
            actor_user_id=user.id,
            entity_id=request.id,
            metadata={
                "request_type": request.request_type,
                "subject_type": request.subject_type,
                "status": request.status,
            },
        )
        self.db.commit()
        self.db.refresh(request)
        return self._read_request(request, requester=user)

    def review_request(
        self, user: User, request_id: str, payload: DataGovernanceRequestReview
    ) -> DataGovernanceRequestRead:
        self._require_org_admin(user)
        organization_id = self._organization_id(user)
        request = self.db.scalar(
            select(DataGovernanceRequest).where(
                DataGovernanceRequest.organization_id == organization_id,
                DataGovernanceRequest.id == request_id,
            )
        )
        if not request:
            raise HTTPException(status_code=404, detail="Data governance request not found")
        if request.status != "open":
            raise HTTPException(status_code=400, detail="Data governance request is already closed")
        request.status = payload.status
        request.resolution_notes = payload.resolution_notes
        request.reviewed_by_user_id = user.id
        request.resolved_at = datetime.utcnow()
        AuditService(self.db).record(
            action=AuditAction.UPDATE,
            entity_type="data_governance_request",
            organization_id=organization_id,
            actor_user_id=user.id,
            entity_id=request.id,
            metadata={"status": request.status, "request_type": request.request_type},
        )
        self.db.commit()
        self.db.refresh(request)
        return self._read_request(request, requester=request.requested_by)

    def _settings_for_org(self, organization_id: str) -> OrganizationPrivacySettings:
        settings = self.db.scalar(
            select(OrganizationPrivacySettings).where(
                OrganizationPrivacySettings.organization_id == organization_id
            )
        )
        if settings:
            return settings
        settings = OrganizationPrivacySettings(organization_id=organization_id)
        self.db.add(settings)
        self.db.flush()
        return settings

    def _organization_id(self, user: User) -> str:
        if not user.organization_id:
            raise HTTPException(status_code=400, detail="User is not attached to an organization")
        return user.organization_id

    def _require_org_admin(self, user: User) -> None:
        if user.role not in {UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN}:
            raise HTTPException(status_code=403, detail="Only organization admins can manage privacy controls")

    def _read_request(
        self, request: DataGovernanceRequest, *, requester: User | None
    ) -> DataGovernanceRequestRead:
        reviewer = request.reviewed_by
        return DataGovernanceRequestRead(
            id=request.id,
            organization_id=request.organization_id,
            requested_by_user_id=request.requested_by_user_id,
            requested_by_email=requester.email if requester else None,
            reviewed_by_user_id=request.reviewed_by_user_id,
            reviewed_by_email=reviewer.email if reviewer else None,
            request_type=request.request_type,
            subject_type=request.subject_type,
            subject_id=request.subject_id,
            status=request.status,
            reason=request.reason,
            resolution_notes=request.resolution_notes,
            created_at=request.created_at,
            resolved_at=request.resolved_at,
        )
