from datetime import datetime

from pydantic import BaseModel


class DependencyCheck(BaseModel):
    name: str
    status: str
    latency_ms: float | None = None
    detail: str | None = None


class OperationsStatus(BaseModel):
    status: str
    service: str
    environment: str
    uptime_seconds: float
    generated_at: datetime
    checks: list[DependencyCheck]
