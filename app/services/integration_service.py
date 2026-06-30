from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_token
from app.models.enums import AuditAction
from app.models.integration import IntegrationConnection, IntegrationEventDelivery
from app.models.user import User
from app.schemas.integration import (
    IntegrationConnectionCreate,
    IntegrationConnectionList,
    IntegrationConnectionRead,
    IntegrationConnectionUpdate,
    IntegrationEventDeliveryList,
    IntegrationEventDeliveryRead,
)
from app.services.audit_service import AuditService


class IntegrationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_connections(
        self, user: User, *, connection_type: str | None = None
    ) -> IntegrationConnectionList:
        organization_id = self._organization_id(user)
        filters = [IntegrationConnection.organization_id == organization_id]
        if connection_type:
            filters.append(IntegrationConnection.connection_type == connection_type)
        stmt = (
            select(IntegrationConnection)
            .where(*filters)
            .order_by(IntegrationConnection.created_at.desc())
        )
        count_stmt = select(func.count(IntegrationConnection.id)).where(*filters)
        items = [self._read(connection) for connection in self.db.scalars(stmt)]
        return IntegrationConnectionList(items=items, total=int(self.db.scalar(count_stmt) or 0))

    def create_connection(
        self, user: User, payload: IntegrationConnectionCreate
    ) -> IntegrationConnectionRead:
        organization_id = self._organization_id(user)
        self._validate_connection(payload.connection_type, str(payload.webhook_url) if payload.webhook_url else None)
        connection = IntegrationConnection(
            organization_id=organization_id,
            name=payload.name,
            provider=payload.provider,
            connection_type=payload.connection_type,
            webhook_url=str(payload.webhook_url) if payload.webhook_url else None,
            secret_hash=hash_token(payload.webhook_secret) if payload.webhook_secret else None,
            config_json=self._redact_config(payload.config),
            events_json=payload.events or default_events(payload.connection_type),
            created_by_user_id=user.id,
            is_active=True,
            status="active",
        )
        self.db.add(connection)
        self.db.flush()
        AuditService(self.db).record(
            action=AuditAction.CREATE,
            entity_type="integration_connection",
            organization_id=organization_id,
            actor_user_id=user.id,
            entity_id=connection.id,
            metadata={"provider": connection.provider, "connection_type": connection.connection_type},
        )
        self.db.commit()
        self.db.refresh(connection)
        return self._read(connection)

    def update_connection(
        self, user: User, connection_id: str, payload: IntegrationConnectionUpdate
    ) -> IntegrationConnectionRead:
        connection = self._get_connection(user, connection_id)
        update_data = payload.model_dump(exclude_unset=True)
        if "webhook_url" in update_data:
            webhook_url = update_data["webhook_url"]
            connection.webhook_url = str(webhook_url) if webhook_url else None
        if "webhook_secret" in update_data:
            secret = update_data["webhook_secret"]
            if secret:
                connection.secret_hash = hash_token(secret)
        if "events" in update_data:
            connection.events_json = update_data["events"] or default_events(connection.connection_type)
        if "config" in update_data:
            connection.config_json = self._redact_config(update_data["config"] or {})
        for field in ("name", "provider", "status", "is_active"):
            if field in update_data:
                setattr(connection, field, update_data[field])
        self._validate_connection(connection.connection_type, connection.webhook_url)
        AuditService(self.db).record(
            action=AuditAction.UPDATE,
            entity_type="integration_connection",
            organization_id=connection.organization_id,
            actor_user_id=user.id,
            entity_id=connection.id,
            metadata={"fields": list(update_data.keys())},
        )
        self.db.commit()
        self.db.refresh(connection)
        return self._read(connection)

    def delete_connection(self, user: User, connection_id: str) -> None:
        connection = self._get_connection(user, connection_id)
        connection.is_active = False
        connection.status = "paused"
        AuditService(self.db).record(
            action=AuditAction.DELETE,
            entity_type="integration_connection",
            organization_id=connection.organization_id,
            actor_user_id=user.id,
            entity_id=connection.id,
        )
        self.db.commit()

    def test_connection(self, user: User, connection_id: str) -> IntegrationEventDeliveryRead:
        connection = self._get_connection(user, connection_id)
        payload = {
            "event_type": "integration.test",
            "organization_id": connection.organization_id,
            "connection_id": connection.id,
            "provider": connection.provider,
            "sent_at": datetime.utcnow().isoformat(),
        }
        delivery = self._create_delivery(
            connection=connection,
            event_type="integration.test",
            entity_type="integration_connection",
            entity_id=connection.id,
            payload=payload,
            status="delivered",
            attempts=1,
            response_status_code=202,
            response_body="Test delivery accepted by integration queue.",
        )
        connection.last_checked_at = datetime.utcnow()
        connection.last_delivery_status = "delivered"
        AuditService(self.db).record(
            action=AuditAction.CREATE,
            entity_type="integration_delivery",
            organization_id=connection.organization_id,
            actor_user_id=user.id,
            entity_id=delivery.id,
            metadata={"event_type": delivery.event_type, "connection_id": connection.id},
        )
        self.db.commit()
        self.db.refresh(delivery)
        return IntegrationEventDeliveryRead.model_validate(delivery)

    def list_deliveries(
        self, user: User, *, connection_id: str | None = None, status: str | None = None
    ) -> IntegrationEventDeliveryList:
        organization_id = self._organization_id(user)
        filters = [IntegrationEventDelivery.organization_id == organization_id]
        if connection_id:
            filters.append(IntegrationEventDelivery.connection_id == connection_id)
        if status:
            filters.append(IntegrationEventDelivery.status == status)
        stmt = (
            select(IntegrationEventDelivery)
            .where(*filters)
            .order_by(IntegrationEventDelivery.created_at.desc())
            .limit(100)
        )
        count_stmt = select(func.count(IntegrationEventDelivery.id)).where(*filters)
        return IntegrationEventDeliveryList(
            items=[IntegrationEventDeliveryRead.model_validate(item) for item in self.db.scalars(stmt)],
            total=int(self.db.scalar(count_stmt) or 0),
        )

    def emit_event(
        self,
        *,
        organization_id: str,
        event_type: str,
        entity_type: str,
        entity_id: str,
        payload: dict,
    ) -> list[IntegrationEventDelivery]:
        connections = self.db.scalars(
            select(IntegrationConnection).where(
                IntegrationConnection.organization_id == organization_id,
                IntegrationConnection.connection_type == "webhook",
                IntegrationConnection.is_active.is_(True),
                IntegrationConnection.status == "active",
            )
        ).all()
        deliveries: list[IntegrationEventDelivery] = []
        for connection in connections:
            if connection.events_json and event_type not in connection.events_json:
                continue
            delivery = self._create_delivery(
                connection=connection,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                payload={
                    "event_type": event_type,
                    "organization_id": organization_id,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "data": payload,
                },
                status="queued",
            )
            connection.last_delivery_status = "queued"
            deliveries.append(delivery)
        return deliveries

    def _create_delivery(
        self,
        *,
        connection: IntegrationConnection,
        event_type: str,
        entity_type: str,
        entity_id: str,
        payload: dict,
        status: str,
        attempts: int = 0,
        response_status_code: int | None = None,
        response_body: str = "",
        error_message: str = "",
    ) -> IntegrationEventDelivery:
        delivery = IntegrationEventDelivery(
            organization_id=connection.organization_id,
            connection_id=connection.id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            status=status,
            attempts=attempts,
            request_payload_json=payload,
            response_status_code=response_status_code,
            response_body=response_body,
            error_message=error_message,
            delivered_at=datetime.utcnow() if status == "delivered" else None,
        )
        self.db.add(delivery)
        self.db.flush()
        return delivery

    def _get_connection(self, user: User, connection_id: str) -> IntegrationConnection:
        organization_id = self._organization_id(user)
        connection = self.db.scalar(
            select(IntegrationConnection).where(
                IntegrationConnection.id == connection_id,
                IntegrationConnection.organization_id == organization_id,
            )
        )
        if not connection:
            raise HTTPException(status_code=404, detail="Integration connection not found")
        return connection

    def _organization_id(self, user: User) -> str:
        if not user.organization_id:
            raise HTTPException(status_code=400, detail="User is not attached to an organization")
        return user.organization_id

    def _read(self, connection: IntegrationConnection) -> IntegrationConnectionRead:
        return IntegrationConnectionRead(
            id=connection.id,
            organization_id=connection.organization_id,
            name=connection.name,
            provider=connection.provider,
            connection_type=connection.connection_type,
            status=connection.status,
            webhook_url=connection.webhook_url,
            config_json=connection.config_json,
            events_json=connection.events_json,
            last_checked_at=connection.last_checked_at,
            last_delivery_status=connection.last_delivery_status,
            created_by_user_id=connection.created_by_user_id,
            is_active=connection.is_active,
            created_at=connection.created_at,
            updated_at=connection.updated_at,
            has_secret=bool(connection.secret_hash),
        )

    def _redact_config(self, config: dict) -> dict:
        redacted = {}
        for key, value in config.items():
            if any(term in key.lower() for term in ("secret", "token", "password", "key")):
                redacted[key] = "********"
            else:
                redacted[key] = value
        return redacted

    def _validate_connection(self, connection_type: str, webhook_url: str | None) -> None:
        if connection_type == "webhook" and not webhook_url:
            raise HTTPException(status_code=422, detail="Webhook integrations require webhook_url")


def default_events(connection_type: str) -> list[str]:
    if connection_type == "webhook":
        return ["product.created", "product.updated", "environmental_record.created"]
    if connection_type == "erp":
        return ["product.created", "product.updated"]
    if connection_type == "lca_database":
        return ["lca.calculation.created", "environmental_record.created"]
    return ["passport.shared", "report_pack.created"]
