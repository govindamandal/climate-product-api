from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession, require_roles
from app.models.enums import UserRole
from app.schemas.billing import BillingPlanRead, BillingSubscriptionUpdate, BillingSummaryRead
from app.services.billing_service import BillingService

router = APIRouter(prefix="/billing", tags=["Billing And Subscriptions"])


@router.get("/plans", response_model=list[BillingPlanRead])
def billing_plans(db: DbSession) -> list[BillingPlanRead]:
    return BillingService(db).list_plans()


@router.get("/current", response_model=BillingSummaryRead)
def current_billing(user: CurrentUser, db: DbSession) -> BillingSummaryRead:
    return BillingService(db).summary_for_user(user)


@router.patch(
    "/current",
    response_model=BillingSummaryRead,
    dependencies=[Depends(require_roles(UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN))],
)
def update_current_billing(
    payload: BillingSubscriptionUpdate,
    user: CurrentUser,
    db: DbSession,
) -> BillingSummaryRead:
    organization_id = user.organization_id or ""
    return BillingService(db).update_subscription(user, organization_id, payload)
