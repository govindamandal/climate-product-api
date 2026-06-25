from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import AuditAction, UserRole
from app.models.product import Product
from app.models.user import User
from app.models.verification import ProductVerification
from app.schemas.verification import (
    ProductVerificationCreate,
    ProductVerificationList,
    ProductVerificationRead,
    ProductVerificationReview,
)
from app.services.audit_service import AuditService


class ProductVerificationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_requests(
        self,
        user: User,
        *,
        status: str | None = None,
        product_id: str | None = None,
    ) -> ProductVerificationList:
        organization_id = self._organization_id(user)
        filters = [ProductVerification.organization_id == organization_id]
        if status:
            filters.append(ProductVerification.status == status)
        if product_id:
            filters.append(ProductVerification.product_id == product_id)
        stmt = (
            select(ProductVerification, Product, User)
            .join(Product, ProductVerification.product_id == Product.id)
            .outerjoin(User, ProductVerification.requested_by_user_id == User.id)
            .where(*filters)
            .order_by(ProductVerification.created_at.desc())
        )
        count_stmt = select(func.count(ProductVerification.id)).where(*filters)
        rows = self.db.execute(stmt).all()
        return ProductVerificationList(
            items=[self._read(verification, product=product, requester=requester) for verification, product, requester in rows],
            total=int(self.db.scalar(count_stmt) or 0),
        )

    def create_request(self, user: User, payload: ProductVerificationCreate) -> ProductVerificationRead:
        organization_id = self._organization_id(user)
        product = self._product_for_org(organization_id, payload.product_id)
        existing = self.db.scalar(
            select(ProductVerification).where(
                ProductVerification.organization_id == organization_id,
                ProductVerification.product_id == product.id,
                ProductVerification.status == "submitted",
            )
        )
        if existing:
            raise HTTPException(status_code=409, detail="Product already has a submitted verification request")
        verification = ProductVerification(
            organization_id=organization_id,
            product_id=product.id,
            requested_by_user_id=user.id,
            verification_type=payload.verification_type,
            scope=payload.scope,
            evidence_summary=payload.evidence_summary,
            requester_notes=payload.requester_notes,
        )
        self.db.add(verification)
        self.db.flush()
        AuditService(self.db).record(
            action=AuditAction.CREATE,
            entity_type="product_verification",
            organization_id=organization_id,
            actor_user_id=user.id,
            entity_id=verification.id,
            metadata={"product_id": product.id, "status": verification.status},
        )
        self.db.commit()
        self.db.refresh(verification)
        return self._read(verification, product=product, requester=user)

    def review_request(
        self, user: User, verification_id: str, payload: ProductVerificationReview
    ) -> ProductVerificationRead:
        if user.role not in {UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN}:
            raise HTTPException(status_code=403, detail="Only organization admins can review verification requests")
        organization_id = self._organization_id(user)
        verification = self.db.scalar(
            select(ProductVerification).where(
                ProductVerification.organization_id == organization_id,
                ProductVerification.id == verification_id,
            )
        )
        if not verification:
            raise HTTPException(status_code=404, detail="Verification request not found")
        if verification.status != "submitted":
            raise HTTPException(status_code=400, detail="Verification request has already been reviewed")
        product = self._product_for_org(organization_id, verification.product_id)
        verification.status = payload.status
        verification.reviewer_notes = payload.reviewer_notes
        verification.reviewed_by_user_id = user.id
        verification.reviewed_at = datetime.utcnow()
        AuditService(self.db).record(
            action=AuditAction.UPDATE,
            entity_type="product_verification",
            organization_id=organization_id,
            actor_user_id=user.id,
            entity_id=verification.id,
            metadata={"product_id": product.id, "status": verification.status},
        )
        self.db.commit()
        self.db.refresh(verification)
        return self._read(verification, product=product, requester=verification.requested_by)

    def _organization_id(self, user: User) -> str:
        if not user.organization_id:
            raise HTTPException(status_code=400, detail="User is not attached to an organization")
        return user.organization_id

    def _product_for_org(self, organization_id: str, product_id: str) -> Product:
        product = self.db.scalar(
            select(Product).where(Product.organization_id == organization_id, Product.id == product_id)
        )
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product

    def _read(
        self,
        verification: ProductVerification,
        *,
        product: Product,
        requester: User | None,
    ) -> ProductVerificationRead:
        reviewer = verification.reviewed_by
        return ProductVerificationRead(
            id=verification.id,
            organization_id=verification.organization_id,
            product_id=verification.product_id,
            product_name=product.name,
            product_category=product.category,
            requested_by_user_id=verification.requested_by_user_id,
            requested_by_email=requester.email if requester else None,
            reviewed_by_user_id=verification.reviewed_by_user_id,
            reviewed_by_email=reviewer.email if reviewer else None,
            status=verification.status,
            verification_type=verification.verification_type,
            scope=verification.scope,
            evidence_summary=verification.evidence_summary,
            requester_notes=verification.requester_notes,
            reviewer_notes=verification.reviewer_notes,
            submitted_at=verification.submitted_at,
            reviewed_at=verification.reviewed_at,
            created_at=verification.created_at,
            updated_at=verification.updated_at,
        )
