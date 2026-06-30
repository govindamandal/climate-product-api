from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession, require_roles
from app.models.enums import UserRole
from app.schemas.integration import (
    IntegrationConnectionCreate,
    IntegrationConnectionList,
    IntegrationConnectionRead,
    IntegrationConnectionUpdate,
    IntegrationEventDeliveryList,
    IntegrationEventDeliveryRead,
)
from app.services.integration_service import IntegrationService

router = APIRouter(
    prefix="/integrations",
    tags=["Integrations"],
    dependencies=[Depends(require_roles(UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN))],
)


@router.get("/connections", response_model=IntegrationConnectionList)
def list_connections(
    user: CurrentUser,
    db: DbSession,
    connection_type: str | None = None,
) -> IntegrationConnectionList:
    return IntegrationService(db).list_connections(user, connection_type=connection_type)


@router.post("/connections", response_model=IntegrationConnectionRead, status_code=201)
def create_connection(
    payload: IntegrationConnectionCreate,
    user: CurrentUser,
    db: DbSession,
) -> IntegrationConnectionRead:
    return IntegrationService(db).create_connection(user, payload)


@router.patch("/connections/{connection_id}", response_model=IntegrationConnectionRead)
def update_connection(
    connection_id: str,
    payload: IntegrationConnectionUpdate,
    user: CurrentUser,
    db: DbSession,
) -> IntegrationConnectionRead:
    return IntegrationService(db).update_connection(user, connection_id, payload)


@router.delete("/connections/{connection_id}", status_code=204)
def delete_connection(connection_id: str, user: CurrentUser, db: DbSession) -> None:
    IntegrationService(db).delete_connection(user, connection_id)


@router.post("/connections/{connection_id}/test", response_model=IntegrationEventDeliveryRead)
def test_connection(
    connection_id: str,
    user: CurrentUser,
    db: DbSession,
) -> IntegrationEventDeliveryRead:
    return IntegrationService(db).test_connection(user, connection_id)


@router.get("/deliveries", response_model=IntegrationEventDeliveryList)
def list_deliveries(
    user: CurrentUser,
    db: DbSession,
    connection_id: str | None = None,
    status: str | None = None,
) -> IntegrationEventDeliveryList:
    return IntegrationService(db).list_deliveries(
        user,
        connection_id=connection_id,
        status=status,
    )
