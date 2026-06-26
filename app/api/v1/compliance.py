from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.compliance import (
    ComplianceReportRequest,
    ComplianceReportResponse,
    ProfessionalReportPackCreate,
    ProfessionalReportPackList,
    ProfessionalReportPackRead,
)
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


@router.get("/report-packs", response_model=ProfessionalReportPackList)
def list_professional_report_packs(
    user: CurrentUser,
    db: DbSession,
    product_id: str | None = None,
    report_type: str | None = None,
) -> ProfessionalReportPackList:
    return ComplianceReportService(db).list_report_packs(
        user,
        product_id=product_id,
        report_type=report_type,
    )


@router.post("/report-packs", response_model=ProfessionalReportPackRead, status_code=201)
def create_professional_report_pack(
    payload: ProfessionalReportPackCreate, user: CurrentUser, db: DbSession
) -> ProfessionalReportPackRead:
    return ComplianceReportService(db).create_report_pack(user, payload)
