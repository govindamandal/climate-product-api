from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.certificate import CertificateExtraction
from app.repositories.base import Repository


class CertificateExtractionRepository(Repository[CertificateExtraction]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, CertificateExtraction)

    def list_for_org(self, organization_id: str) -> tuple[list[CertificateExtraction], int]:
        stmt = (
            select(CertificateExtraction)
            .where(CertificateExtraction.organization_id == organization_id)
            .order_by(CertificateExtraction.created_at.desc())
        )
        count_stmt = select(func.count(CertificateExtraction.id)).where(
            CertificateExtraction.organization_id == organization_id
        )
        return list(self.db.scalars(stmt)), int(self.db.scalar(count_stmt) or 0)

    def get_for_org(self, organization_id: str, extraction_id: str) -> CertificateExtraction | None:
        return self.db.scalar(
            select(CertificateExtraction).where(
                CertificateExtraction.organization_id == organization_id,
                CertificateExtraction.id == extraction_id,
            )
        )
