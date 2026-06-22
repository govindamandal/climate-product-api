from fastapi import APIRouter, File, Form, UploadFile

from app.api.deps import CurrentUser, DbSession
from app.models.certificate import CertificateExtraction

router = APIRouter(prefix="/certificates", tags=["Certificate Extraction"])


@router.post("/extract", status_code=201)
async def extract_certificate(
    user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
    product_id: str | None = Form(default=None),
) -> dict:
    content = await file.read()
    guessed_name = file.filename.rsplit(".", 1)[0].replace("_", " ").title()
    extraction = CertificateExtraction(
        organization_id=user.organization_id or "",
        product_id=product_id,
        file_name=file.filename,
        certification_name=guessed_name,
        compliance_information="Pending manual verification from uploaded certificate.",
        extracted_json={
            "bytes": len(content),
            "workflow": "llm_document_extraction_stub",
            "fields": ["certification_name", "expiry_date", "emission_value"],
        },
    )
    db.add(extraction)
    db.commit()
    db.refresh(extraction)
    return {
        "id": extraction.id,
        "status": extraction.status,
        "certification_name": extraction.certification_name,
        "requires_manual_review": True,
    }
