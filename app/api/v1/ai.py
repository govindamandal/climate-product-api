from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.ai import AdvisorResponse, ReportResponse
from app.services.ai_service import SustainabilityAdvisor

router = APIRouter(prefix="/ai", tags=["AI Sustainability"])


@router.post("/products/{product_id}/advisor", response_model=AdvisorResponse)
def product_advisor(product_id: str, user: CurrentUser, db: DbSession) -> AdvisorResponse:
    return SustainabilityAdvisor(db).analyze(user, product_id)


@router.post("/products/{product_id}/report", response_model=ReportResponse)
def product_report(product_id: str, user: CurrentUser, db: DbSession) -> ReportResponse:
    return SustainabilityAdvisor(db).report(user, product_id)
