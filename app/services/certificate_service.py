import re
from datetime import date

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.models.certificate import CertificateExtraction
from app.models.enums import AuditAction
from app.models.user import User
from app.repositories.certificates import CertificateExtractionRepository
from app.schemas.certificate import (
    CertificateExtractionList,
    CertificateExtractionUpdate,
)
from app.services.audit_service import AuditService


class CertificateExtractionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.certificates = CertificateExtractionRepository(db)

    def list_extractions(self, user: User) -> CertificateExtractionList:
        organization_id = self._organization_id(user)
        items, total = self.certificates.list_for_org(organization_id)
        return CertificateExtractionList(items=items, total=total)

    async def extract(self, user: User, file: UploadFile, product_id: str | None) -> CertificateExtraction:
        organization_id = self._organization_id(user)
        content = await file.read()
        text = self._decode_content(content)
        parsed = self._extract_fields(file.filename, text, len(content))
        extraction = CertificateExtraction(
            organization_id=organization_id,
            product_id=product_id or None,
            file_name=file.filename,
            certification_name=parsed["certification_name"],
            expiry_date=parsed["expiry_date"],
            emission_value=parsed["emission_value"],
            compliance_information=parsed["compliance_information"],
            extracted_json=parsed["extracted_json"],
            status="needs_review",
        )
        self.db.add(extraction)
        AuditService(self.db).record(
            actor_user_id=user.id,
            organization_id=organization_id,
            action=AuditAction.CREATE,
            entity_type="certificate_extraction",
            entity_id=extraction.id,
            metadata={"file_name": file.filename, "requires_manual_review": True},
        )
        self.db.commit()
        self.db.refresh(extraction)
        return extraction

    def update_extraction(
        self, user: User, extraction_id: str, payload: CertificateExtractionUpdate
    ) -> CertificateExtraction:
        organization_id = self._organization_id(user)
        extraction = self.certificates.get_for_org(organization_id, extraction_id)
        if not extraction:
            raise HTTPException(status_code=404, detail="Certificate extraction not found")
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(extraction, field, value)
        AuditService(self.db).record(
            actor_user_id=user.id,
            organization_id=organization_id,
            action=AuditAction.UPDATE,
            entity_type="certificate_extraction",
            entity_id=extraction.id,
            metadata={"status": extraction.status},
        )
        self.db.commit()
        self.db.refresh(extraction)
        return extraction

    def _organization_id(self, user: User) -> str:
        if not user.organization_id:
            raise HTTPException(status_code=400, detail="User is not attached to an organization")
        return user.organization_id

    def _decode_content(self, content: bytes) -> str:
        return content[:20000].decode("utf-8", errors="ignore")

    def _extract_fields(self, file_name: str, text: str, byte_count: int) -> dict:
        searchable = f"{file_name}\n{text}"
        guessed_name = file_name.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
        known_certification = re.search(
            r"(EPD\s*(?:EN\s*)?15804|ISO\s*14025|Cradle\s*to\s*Cradle|FSC|PEFC|BREEAM|LEED)",
            searchable,
            re.IGNORECASE,
        )
        expiry = self._find_expiry_date(searchable)
        emission = self._find_emission_value(searchable)
        certification_name = known_certification.group(1).upper() if known_certification else guessed_name
        compliance = (
            "Extracted fields require manual verification before compliance use."
            if not known_certification
            else f"{certification_name} detected; verify issuer, scope, and declared unit."
        )
        return {
            "certification_name": certification_name,
            "expiry_date": expiry,
            "emission_value": emission,
            "compliance_information": compliance,
            "extracted_json": {
                "bytes": byte_count,
                "workflow": "deterministic_document_extraction",
                "confidence": {
                    "certification_name": 0.82 if known_certification else 0.48,
                    "expiry_date": 0.72 if expiry else 0.2,
                    "emission_value": 0.74 if emission is not None else 0.2,
                },
                "manual_review_required": True,
            },
        }

    def _find_expiry_date(self, text: str) -> date | None:
        match = re.search(
            r"(?:expir(?:y|es|ation)|valid\s+until)\D*(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})",
            text,
            re.IGNORECASE,
        )
        if not match:
            return None
        year, month, day = (int(value) for value in match.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None

    def _find_emission_value(self, text: str) -> float | None:
        match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:kg\s*)?(?:CO2e|CO2-eq|CO₂e)",
            text,
            re.IGNORECASE,
        )
        return float(match.group(1)) if match else None
