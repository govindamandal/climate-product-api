from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.enums import AuditAction
from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization import AuditLogRead


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        action: AuditAction,
        entity_type: str,
        organization_id: str | None = None,
        actor_user_id: str | None = None,
        entity_id: str | None = None,
        metadata: dict | None = None,
    ) -> AuditLog:
        log = AuditLog(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata or {},
        )
        self.db.add(log)
        self.db.flush()
        return log

    def list_logs(
        self,
        *,
        organization_id: str | None = None,
        limit: int = 25,
        action: str | None = None,
        entity_type: str | None = None,
        search: str | None = None,
    ) -> tuple[list[AuditLogRead], int]:
        bounded_limit = max(1, min(limit, 200))
        filters = []
        if organization_id:
            filters.append(AuditLog.organization_id == organization_id)
        if action:
            try:
                filters.append(AuditLog.action == AuditAction(action))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Unsupported audit action") from exc
        if entity_type:
            filters.append(AuditLog.entity_type == entity_type)
        if search:
            like = f"%{search}%"
            filters.append(
                or_(
                    AuditLog.entity_type.ilike(like),
                    AuditLog.entity_id.ilike(like),
                    User.email.ilike(like),
                    User.full_name.ilike(like),
                    Organization.name.ilike(like),
                )
            )

        stmt = (
            select(AuditLog, User, Organization)
            .outerjoin(User, AuditLog.actor_user_id == User.id)
            .outerjoin(Organization, AuditLog.organization_id == Organization.id)
            .where(*filters)
            .order_by(AuditLog.created_at.desc())
            .limit(bounded_limit)
        )
        count_stmt = (
            select(func.count(AuditLog.id))
            .outerjoin(User, AuditLog.actor_user_id == User.id)
            .outerjoin(Organization, AuditLog.organization_id == Organization.id)
            .where(*filters)
        )
        rows = self.db.execute(stmt).all()
        return [
            self._read(log, actor=actor, organization=organization)
            for log, actor, organization in rows
        ], int(self.db.scalar(count_stmt) or 0)

    def _read(
        self, log: AuditLog, *, actor: User | None, organization: Organization | None
    ) -> AuditLogRead:
        return AuditLogRead(
            id=log.id,
            organization_id=log.organization_id,
            actor_user_id=log.actor_user_id,
            action=log.action.value,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            metadata_json=log.metadata_json or {},
            created_at=log.created_at,
            actor_email=actor.email if actor else None,
            actor_full_name=actor.full_name if actor else None,
            organization_name=organization.name if organization else None,
            description=describe_audit_log(log),
        )


def describe_audit_log(log: AuditLog) -> str:
    entity = log.entity_type.replace("_", " ")
    action = log.action.value
    metadata = log.metadata_json or {}
    if log.entity_type == "team_member" and metadata:
        fields = ", ".join(metadata.keys())
        return f"{action.title()} team member fields: {fields}"
    if log.entity_type == "user_invite":
        return "Created an organization invite"
    if log.entity_type == "subscription":
        status = metadata.get("subscription_status", "updated")
        return f"Updated subscription status to {status}"
    if log.entity_type == "billing_subscription":
        plan = metadata.get("plan_key", "plan")
        cycle = metadata.get("billing_cycle", "cycle")
        return f"Updated billing subscription to {plan} ({cycle})"
    if log.entity_type == "product_import":
        return f"Imported {metadata.get('created', 0)} product(s)"
    if log.entity_type == "product_verification":
        return f"{action.title()} product verification as {metadata.get('status', 'submitted')}"
    if log.entity_type == "privacy_settings":
        return "Updated organization privacy controls"
    if log.entity_type == "data_governance_request":
        request_type = str(metadata.get("request_type", "data")).replace("_", " ")
        status = metadata.get("status", "open")
        return f"{action.title()} {request_type} request as {status}"
    if log.entity_type == "professional_report_pack":
        report_type = str(metadata.get("report_type", "professional")).replace("_", " ")
        return f"Created {report_type} report pack"
    if log.entity_type == "password_reset":
        return "Requested password reset instructions"
    if log.entity_type == "invite_acceptance":
        return "Accepted an organization invite"
    return f"{action.title()} {entity}"
