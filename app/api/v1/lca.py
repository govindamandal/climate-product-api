from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.lca import (
    EmissionFactorRead,
    LcaCalculationCreate,
    LcaCalculationList,
    LcaCalculationRead,
)
from app.services.lca_service import LcaService

router = APIRouter(prefix="/lca", tags=["LCA Calculations"])


@router.get("/emission-factors", response_model=list[EmissionFactorRead])
def emission_factors(
    user: CurrentUser,
    db: DbSession,
    category: str | None = None,
    stage: str | None = None,
    search: str | None = None,
) -> list[EmissionFactorRead]:
    return LcaService(db).list_factors(user, category=category, stage=stage, search=search)


@router.post("/products/{product_id}/calculations", response_model=LcaCalculationRead, status_code=201)
def create_calculation(
    product_id: str,
    payload: LcaCalculationCreate,
    user: CurrentUser,
    db: DbSession,
) -> LcaCalculationRead:
    return LcaService(db).create_calculation(user, product_id, payload)


@router.get("/products/{product_id}/calculations", response_model=LcaCalculationList)
def product_calculations(product_id: str, user: CurrentUser, db: DbSession) -> LcaCalculationList:
    return LcaService(db).list_calculations(user, product_id)
