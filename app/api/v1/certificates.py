from fastapi import APIRouter, File, Form, UploadFile

from app.api.deps import CurrentUser, DbSession
from app.schemas.certificate import (
    CertificateExtractionList,
    CertificateExtractionRead,
    CertificateExtractionUpdate,
)
from app.services.certificate_service import CertificateExtractionService

router = APIRouter(prefix="/certificates", tags=["Certificate Extraction"])


@router.get("", response_model=CertificateExtractionList)
def list_certificate_extractions(user: CurrentUser, db: DbSession) -> CertificateExtractionList:
    return CertificateExtractionService(db).list_extractions(user)


@router.post("/extract", response_model=CertificateExtractionRead, status_code=201)
async def extract_certificate(
    user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
    product_id: str | None = Form(default=None),
) -> CertificateExtractionRead:
    return await CertificateExtractionService(db).extract(user, file, product_id)


@router.patch("/{extraction_id}", response_model=CertificateExtractionRead)
def update_certificate_extraction(
    extraction_id: str,
    payload: CertificateExtractionUpdate,
    user: CurrentUser,
    db: DbSession,
) -> CertificateExtractionRead:
    return CertificateExtractionService(db).update_extraction(user, extraction_id, payload)
