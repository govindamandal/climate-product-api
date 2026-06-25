from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.compliance import ComplianceReportRequest, ComplianceReportResponse
from app.services.compliance_service import ComplianceReportService

router = APIRouter(prefix="/compliance", tags=["Compliance Reports"])


@router.post("/reports", response_model=ComplianceReportResponse)
def build_compliance_report(
    payload: ComplianceReportRequest, user: CurrentUser, db: DbSession
) -> ComplianceReportResponse:
    return ComplianceReportService(db).build(user, payload)


@router.post("/india/reports", response_model=ComplianceReportResponse)
def build_india_compliance_report(
    payload: ComplianceReportRequest, user: CurrentUser, db: DbSession
) -> ComplianceReportResponse:
    return ComplianceReportService(db).build_india_readiness(user, payload)
