from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


BillingCycle = Literal["monthly", "annual"]
BillingStatus = Literal["trial", "active", "past_due", "canceled"]


class BillingPlanRead(BaseModel):
    key: str
    name: str
    description: str
    monthly_price_inr: int
    annual_price_inr: int
    seats_included: int
    products_included: int
    features: list[str]


class BillingUsageRead(BaseModel):
    users: int
    products: int
    seats_included: int
    products_included: int
    seat_utilization_pct: float
    product_utilization_pct: float


class BillingInvoiceRead(BaseModel):
    id: str
    invoice_number: str
    amount_inr: int
    status: str
    invoice_url: str | None
    issued_at: datetime
    due_at: datetime | None
    paid_at: datetime | None

    model_config = {"from_attributes": True}


class BillingSubscriptionRead(BaseModel):
    id: str
    organization_id: str
    plan_key: str
    plan_name: str
    billing_cycle: BillingCycle
    status: BillingStatus
    seats_included: int
    products_included: int
    provider: str
    provider_customer_id: str | None
    provider_subscription_id: str | None
    trial_ends_at: datetime
    current_period_ends_at: datetime
    cancel_at_period_end: bool
    updated_at: datetime


class BillingSummaryRead(BaseModel):
    subscription: BillingSubscriptionRead
    current_plan: BillingPlanRead
    usage: BillingUsageRead
    invoices: list[BillingInvoiceRead]


class BillingSubscriptionUpdate(BaseModel):
    plan_key: str = Field(min_length=2, max_length=40)
    billing_cycle: BillingCycle = "monthly"
