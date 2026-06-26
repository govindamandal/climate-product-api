from fastapi import APIRouter, Depends

from app.api.deps import DbSession, require_roles
from app.models.enums import UserRole
from app.schemas.operations import OperationsStatus
from app.services.operations_service import OperationsService

router = APIRouter(
    prefix="/operations",
    tags=["Operational Reliability"],
    dependencies=[Depends(require_roles(UserRole.SUPER_ADMIN))],
)


@router.get("/status", response_model=OperationsStatus)
def operations_status(db: DbSession) -> OperationsStatus:
    return OperationsService(db).status()
