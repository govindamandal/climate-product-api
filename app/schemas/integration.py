from datetime import datetime
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator

ConnectionType = Literal["webhook", "erp", "lca_database", "storage"]
IntegrationStatus = Literal["active", "paused", "error"]
DeliveryStatus = Literal["queued", "delivered", "failed"]


class IntegrationConnectionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    provider: str = Field(min_length=2, max_length=80)
    connection_type: ConnectionType
    webhook_url: AnyHttpUrl | None = None
    webhook_secret: str | None = Field(default=None, min_length=8, max_length=255)
    events: list[str] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)

    @field_validator("events")
    @classmethod
    def clean_events(cls, value: list[str]) -> list[str]:
        cleaned = []
        for item in value:
            event = item.strip().lower()
            if event and event not in cleaned:
                cleaned.append(event)
        return cleaned


class IntegrationConnectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    provider: str | None = Field(default=None, min_length=2, max_length=80)
    status: IntegrationStatus | None = None
    webhook_url: AnyHttpUrl | None = None
    webhook_secret: str | None = Field(default=None, min_length=8, max_length=255)
    events: list[str] | None = None
    config: dict | None = None
    is_active: bool | None = None

    @field_validator("events")
    @classmethod
    def clean_events(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = []
        for item in value:
            event = item.strip().lower()
            if event and event not in cleaned:
                cleaned.append(event)
        return cleaned


class IntegrationConnectionRead(BaseModel):
    id: str
    organization_id: str
    name: str
    provider: str
    connection_type: str
    status: str
    webhook_url: str | None
    config_json: dict
    events_json: list
    last_checked_at: datetime | None
    last_delivery_status: str | None
    created_by_user_id: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    has_secret: bool

    model_config = {"from_attributes": True}


class IntegrationConnectionList(BaseModel):
    items: list[IntegrationConnectionRead]
    total: int


class IntegrationEventDeliveryRead(BaseModel):
    id: str
    organization_id: str
    connection_id: str | None
    event_type: str
    entity_type: str
    entity_id: str
    status: str
    attempts: int
    request_payload_json: dict
    response_status_code: int | None
    response_body: str
    error_message: str
    created_at: datetime
    delivered_at: datetime | None

    model_config = {"from_attributes": True}


class IntegrationEventDeliveryList(BaseModel):
    items: list[IntegrationEventDeliveryRead]
    total: int
