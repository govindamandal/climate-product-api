from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.product import PassportRead
from app.services.passport_service import PassportService

router = APIRouter(prefix="/passports", tags=["Digital Product Passports"])


@router.get("/{product_id}", response_model=PassportRead)
def generate_passport(product_id: str, user: CurrentUser, db: DbSession) -> PassportRead:
    return PassportService(db).generate(user, product_id)
