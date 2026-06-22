from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.enums import AuditAction


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
