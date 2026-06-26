from datetime import datetime, timedelta
from typing import NamedTuple

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.billing import BillingInvoice, BillingSubscription
from app.models.enums import AuditAction, SubscriptionStatus, UserRole
from app.models.organization import Organization
from app.models.product import Product
from app.models.user import User
from app.schemas.billing import (
    BillingInvoiceRead,
    BillingPlanRead,
    BillingSubscriptionRead,
    BillingSubscriptionUpdate,
    BillingSummaryRead,
    BillingUsageRead,
)
from app.services.audit_service import AuditService


class PlanDefinition(NamedTuple):
    key: str
    name: str
    description: str
    monthly_price_inr: int
    annual_price_inr: int
    seats_included: int
    products_included: int
    features: list[str]


PLAN_CATALOG = {
    "starter": PlanDefinition(
        key="starter",
        name="Starter",
        description="For pilots, demos, and early product digitization.",
        monthly_price_inr=0,
        annual_price_inr=0,
        seats_included=3,
        products_included=25,
        features=["Digital Product Passports", "Basic sustainability dashboard", "CSV product import"],
    ),
    "growth": PlanDefinition(
        key="growth",
        name="Growth",
        description="For manufacturers managing multiple material lines and buyer evidence requests.",
        monthly_price_inr=9999,
        annual_price_inr=99900,
        seats_included=10,
        products_included=200,
        features=["AI advisory and reports", "Verification workflow", "India compliance reports", "Public DPP sharing"],
    ),
    "enterprise": PlanDefinition(
        key="enterprise",
        name="Enterprise",
        description="For multi-plant manufacturers with private controls and procurement integrations.",
        monthly_price_inr=0,
        annual_price_inr=0,
        seats_included=100,
        products_included=5000,
        features=["Custom limits", "Dedicated onboarding", "Advanced audit support", "Contract billing"],
    ),
}


class BillingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_plans(self) -> list[BillingPlanRead]:
        return [self._plan_read(plan) for plan in PLAN_CATALOG.values()]

    def summary_for_user(self, user: User) -> BillingSummaryRead:
        organization_id = self._organization_id(user)
        subscription = self._subscription_for_org(organization_id)
        self.db.commit()
        self.db.refresh(subscription)
        return self._summary(subscription)

    def update_subscription(
        self, user: User, organization_id: str, payload: BillingSubscriptionUpdate
    ) -> BillingSummaryRead:
        self._require_org_admin(user)
        if user.role != UserRole.SUPER_ADMIN and user.organization_id != organization_id:
            raise HTTPException(status_code=404, detail="Organization not found")
        if payload.plan_key not in PLAN_CATALOG:
            raise HTTPException(status_code=400, detail="Unknown billing plan")
        organization = self.db.get(Organization, organization_id)
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")
        subscription = self._subscription_for_org(organization_id)
        plan = PLAN_CATALOG[payload.plan_key]
        subscription.plan_key = payload.plan_key
        subscription.billing_cycle = payload.billing_cycle
        subscription.seats_included = plan.seats_included
        subscription.products_included = plan.products_included
        subscription.status = "active" if payload.plan_key != "starter" else "trial"
        subscription.current_period_ends_at = datetime.utcnow() + timedelta(days=365 if payload.billing_cycle == "annual" else 30)
        subscription.cancel_at_period_end = False
        organization.subscription_status = (
            SubscriptionStatus.ACTIVE if subscription.status == "active" else SubscriptionStatus.TRIAL
        )
        AuditService(self.db).record(
            action=AuditAction.UPDATE,
            entity_type="billing_subscription",
            organization_id=organization_id,
            actor_user_id=user.id,
            entity_id=subscription.id,
            metadata={
                "plan_key": subscription.plan_key,
                "billing_cycle": subscription.billing_cycle,
                "status": subscription.status,
            },
        )
        self.db.commit()
        self.db.refresh(subscription)
        return self._summary(subscription)

    def _subscription_for_org(self, organization_id: str) -> BillingSubscription:
        subscription = self.db.scalar(
            select(BillingSubscription).where(BillingSubscription.organization_id == organization_id)
        )
        if subscription:
            return subscription
        subscription = BillingSubscription(organization_id=organization_id)
        self.db.add(subscription)
        self.db.flush()
        return subscription

    def _summary(self, subscription: BillingSubscription) -> BillingSummaryRead:
        plan = PLAN_CATALOG.get(subscription.plan_key, PLAN_CATALOG["starter"])
        users = int(self.db.scalar(select(func.count(User.id)).where(User.organization_id == subscription.organization_id)) or 0)
        products = int(
            self.db.scalar(select(func.count(Product.id)).where(Product.organization_id == subscription.organization_id)) or 0
        )
        invoices = list(
            self.db.scalars(
                select(BillingInvoice)
                .where(BillingInvoice.organization_id == subscription.organization_id)
                .order_by(BillingInvoice.issued_at.desc())
                .limit(6)
            )
        )
        return BillingSummaryRead(
            subscription=self._subscription_read(subscription, plan),
            current_plan=self._plan_read(plan),
            usage=BillingUsageRead(
                users=users,
                products=products,
                seats_included=subscription.seats_included,
                products_included=subscription.products_included,
                seat_utilization_pct=self._percentage(users, subscription.seats_included),
                product_utilization_pct=self._percentage(products, subscription.products_included),
            ),
            invoices=[BillingInvoiceRead.model_validate(invoice) for invoice in invoices],
        )

    def _subscription_read(
        self, subscription: BillingSubscription, plan: PlanDefinition
    ) -> BillingSubscriptionRead:
        return BillingSubscriptionRead(
            id=subscription.id,
            organization_id=subscription.organization_id,
            plan_key=subscription.plan_key,
            plan_name=plan.name,
            billing_cycle=subscription.billing_cycle,
            status=subscription.status,
            seats_included=subscription.seats_included,
            products_included=subscription.products_included,
            provider=subscription.provider,
            provider_customer_id=subscription.provider_customer_id,
            provider_subscription_id=subscription.provider_subscription_id,
            trial_ends_at=subscription.trial_ends_at,
            current_period_ends_at=subscription.current_period_ends_at,
            cancel_at_period_end=subscription.cancel_at_period_end,
            updated_at=subscription.updated_at,
        )

    def _plan_read(self, plan: PlanDefinition) -> BillingPlanRead:
        return BillingPlanRead(
            key=plan.key,
            name=plan.name,
            description=plan.description,
            monthly_price_inr=plan.monthly_price_inr,
            annual_price_inr=plan.annual_price_inr,
            seats_included=plan.seats_included,
            products_included=plan.products_included,
            features=plan.features,
        )

    def _organization_id(self, user: User) -> str:
        if not user.organization_id:
            raise HTTPException(status_code=400, detail="User is not attached to an organization")
        return user.organization_id

    def _require_org_admin(self, user: User) -> None:
        if user.role not in {UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN}:
            raise HTTPException(status_code=403, detail="Only admins can manage billing")

    def _percentage(self, value: int, limit: int) -> float:
        if limit <= 0:
            return 0
        return round(min(value / limit * 100, 999), 1)
