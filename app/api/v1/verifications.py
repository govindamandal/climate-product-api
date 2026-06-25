from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.verification import (
    ProductVerificationCreate,
    ProductVerificationList,
    ProductVerificationRead,
    ProductVerificationReview,
)
from app.services.verification_service import ProductVerificationService

router = APIRouter(prefix="/verifications", tags=["Verification Workflow"])


@router.get("", response_model=ProductVerificationList)
def list_verifications(
    user: CurrentUser,
    db: DbSession,
    status: str | None = None,
    product_id: str | None = None,
) -> ProductVerificationList:
    return ProductVerificationService(db).list_requests(user, status=status, product_id=product_id)


@router.post("", response_model=ProductVerificationRead, status_code=201)
def create_verification(
    payload: ProductVerificationCreate, user: CurrentUser, db: DbSession
) -> ProductVerificationRead:
    return ProductVerificationService(db).create_request(user, payload)


@router.patch("/{verification_id}/review", response_model=ProductVerificationRead)
def review_verification(
    verification_id: str,
    payload: ProductVerificationReview,
    user: CurrentUser,
    db: DbSession,
) -> ProductVerificationRead:
    return ProductVerificationService(db).review_request(user, verification_id, payload)
