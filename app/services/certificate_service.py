import re
from io import BytesIO
from datetime import date

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader
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
        text = self._decode_content(file.filename, content)
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

    def _decode_content(self, file_name: str, content: bytes) -> str:
        if file_name.lower().endswith(".pdf"):
            try:
                reader = PdfReader(BytesIO(content))
                return "\n".join((page.extract_text() or "") for page in reader.pages)[:50000]
            except Exception:
                return content[:50000].decode("utf-8", errors="ignore")
        return content[:50000].decode("utf-8", errors="ignore")

    def _extract_fields(self, file_name: str, text: str, byte_count: int) -> dict:
        searchable = f"{file_name}\n{text}"
        guessed_name = file_name.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
        certification = self._find_certification(searchable)
        issuer = self._find_labeled_text(searchable, ["issuer", "program operator", "verification body"])
        declaration_number = self._find_labeled_text(
            searchable, ["declaration number", "registration number", "certificate number", "epd number"]
        )
        declared_unit = self._find_labeled_text(searchable, ["declared unit", "functional unit"])
        expiry = self._find_expiry_date(searchable)
        emission = self._find_emission_value(searchable)
        certification_name = certification["value"] if certification else guessed_name
        compliance = (
            "Extracted fields require manual verification before compliance use."
            if not certification
            else f"{certification_name} detected; verify issuer, scope, declared unit, and GWP value."
        )
        field_confidence = {
            "certification_name": 0.9 if certification else 0.45,
            "expiry_date": 0.78 if expiry else 0.2,
            "emission_value": 0.82 if emission is not None else 0.2,
            "issuer": 0.7 if issuer else 0.2,
            "declaration_number": 0.74 if declaration_number else 0.2,
            "declared_unit": 0.72 if declared_unit else 0.2,
        }
        return {
            "certification_name": certification_name,
            "expiry_date": expiry,
            "emission_value": emission,
            "compliance_information": compliance,
            "extracted_json": {
                "bytes": byte_count,
                "characters_extracted": len(text),
                "workflow": "pdf_text_field_extraction",
                "confidence": field_confidence,
                "overall_confidence": round(sum(field_confidence.values()) / len(field_confidence), 2),
                "fields": {
                    "certification_name": certification_name,
                    "issuer": issuer["value"] if issuer else None,
                    "declaration_number": declaration_number["value"] if declaration_number else None,
                    "declared_unit": declared_unit["value"] if declared_unit else None,
                    "expiry_date": expiry.isoformat() if expiry else None,
                    "emission_value": emission,
                },
                "evidence": {
                    "certification_name": certification["evidence"] if certification else None,
                    "issuer": issuer["evidence"] if issuer else None,
                    "declaration_number": declaration_number["evidence"] if declaration_number else None,
                    "declared_unit": declared_unit["evidence"] if declared_unit else None,
                    "expiry_date": self._evidence_for(searchable, "valid") if expiry else None,
                    "emission_value": self._evidence_for(searchable, "co2") if emission is not None else None,
                },
                "manual_review_required": True,
            },
        }

    def _find_certification(self, text: str) -> dict | None:
        match = re.search(
            r"(EPD\s*(?:EN\s*)?15804|EN\s*15804|ISO\s*14025|Cradle\s*to\s*Cradle|FSC|PEFC|BREEAM|LEED)",
            text,
            re.IGNORECASE,
        )
        if not match:
            return None
        value = match.group(1).upper().replace("  ", " ")
        if value == "EN 15804":
            value = "EPD EN 15804"
        return {"value": value, "evidence": self._snippet(text, match.start(), match.end())}

    def _find_labeled_text(self, text: str, labels: list[str]) -> dict | None:
        label_pattern = "|".join(re.escape(label) for label in labels)
        match = re.search(
            rf"(?:{label_pattern})\s*[:#-]?\s*([A-Za-z0-9][A-Za-z0-9 ._/-]{{1,120}})",
            text,
            re.IGNORECASE,
        )
        if not match:
            return None
        value = re.split(r"[\n\r]", match.group(1).strip())[0].strip(" .")
        return {"value": value, "evidence": self._snippet(text, match.start(), match.end())}

    def _find_expiry_date(self, text: str) -> date | None:
        match = re.search(
            r"(?:expir(?:y|es|ation)|valid\s+until|validity)\D*(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})",
            text,
            re.IGNORECASE,
        )
        if not match:
            match = re.search(
                r"(?:expir(?:y|es|ation)|valid\s+until|validity)\D*(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})",
                text,
                re.IGNORECASE,
            )
            if not match:
                return None
            day, month, year = (int(value) for value in match.groups())
            try:
                return date(year, month, day)
            except ValueError:
                return None
        if not match:
            return None
        year, month, day = (int(value) for value in match.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None

    def _find_emission_value(self, text: str) -> float | None:
        match = re.search(
            r"(?:GWP(?:-total)?|global warming potential|A1-A3|carbon footprint)?\D{0,40}"
            r"(\d+(?:\.\d+)?)\s*(?:kg\s*)?(?:CO2e|CO2-eq|CO₂e|kg\s*CO2\s*eq)",
            text,
            re.IGNORECASE,
        )
        return float(match.group(1)) if match else None

    def _evidence_for(self, text: str, needle: str) -> str | None:
        index = text.lower().find(needle.lower())
        if index < 0:
            return None
        return self._snippet(text, index, index + len(needle))

    def _snippet(self, text: str, start: int, end: int) -> str:
        return " ".join(text[max(0, start - 80) : min(len(text), end + 120)].split())
