from datetime import datetime
from time import perf_counter

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.operations import DependencyCheck, OperationsStatus
from app.services.cache_service import CacheService

STARTED_AT = perf_counter()


class OperationsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def status(self) -> OperationsStatus:
        checks = [self._database_check(), self._cache_check()]
        overall = "ok" if all(check.status == "ok" for check in checks) else "degraded"
        return OperationsStatus(
            status=overall,
            service=self.settings.app_name,
            environment=self.settings.environment,
            uptime_seconds=round(perf_counter() - STARTED_AT, 2),
            generated_at=datetime.utcnow(),
            checks=checks,
        )

    def _database_check(self) -> DependencyCheck:
        started_at = perf_counter()
        try:
            self.db.execute(text("SELECT 1"))
            latency_ms = round((perf_counter() - started_at) * 1000, 2)
            return DependencyCheck(name="database", status="ok", latency_ms=latency_ms)
        except Exception as exc:  # noqa: BLE001 - dependency diagnostics should surface error detail.
            latency_ms = round((perf_counter() - started_at) * 1000, 2)
            return DependencyCheck(
                name="database",
                status="error",
                latency_ms=latency_ms,
                detail=str(exc),
            )

    def _cache_check(self) -> DependencyCheck:
        started_at = perf_counter()
        ok, detail = CacheService().health()
        latency_ms = round((perf_counter() - started_at) * 1000, 2)
        return DependencyCheck(
            name="cache",
            status="ok" if ok else "degraded",
            latency_ms=latency_ms,
            detail=detail,
        )
