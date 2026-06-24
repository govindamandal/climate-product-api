from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession, require_roles
from app.models.enums import UserRole
from app.schemas.product import PassportRead, PassportShareRead, PublicPassportRead
from app.services.passport_service import PassportService

router = APIRouter(prefix="/passports", tags=["Digital Product Passports"])


@router.get("/{product_id}", response_model=PassportRead)
def generate_passport(product_id: str, user: CurrentUser, db: DbSession) -> PassportRead:
    return PassportService(db).generate(user, product_id)


@router.post(
    "/{product_id}/shares",
    response_model=PassportShareRead,
    status_code=201,
    dependencies=[Depends(require_roles(UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN))],
)
def create_passport_share(product_id: str, user: CurrentUser, db: DbSession) -> PassportShareRead:
    return PassportService(db).create_share(user, product_id)


@router.get("/public/{token}", response_model=PublicPassportRead)
def public_passport(token: str, db: DbSession) -> PublicPassportRead:
    return PassportService(db).public_passport(token)
