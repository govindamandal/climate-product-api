from time import perf_counter
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from uuid import uuid4

from app.api.v1.router import api_router
from app.api.deps import DbSession
from app.core.config import get_settings
from app.observability.logging import configure_logging
from app.services.cache_service import CacheService

configure_logging()
settings = get_settings()


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started_at = perf_counter()
        request_id = request.headers.get("x-request-id", str(uuid4()))
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        response.headers["x-process-time-ms"] = f"{(perf_counter() - started_at) * 1000:.2f}"
        return response


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Multi-tenant climate product management API with DPP and AI workflows.",
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.get("/health", tags=["System"])
    def health() -> dict:
        return {"status": "ok", "service": settings.app_name}

    @app.get("/ready", tags=["System"])
    def readiness(db: DbSession) -> dict:
        checks: dict[str, dict[str, str]] = {}
        try:
            db.execute(text("SELECT 1"))
            checks["database"] = {"status": "ok"}
        except Exception as exc:  # noqa: BLE001 - readiness should report dependency errors.
            checks["database"] = {"status": "error", "detail": str(exc)}

        checks["cache"] = {"status": "ok" if CacheService().ping() else "degraded"}
        overall_status = "ok" if all(check["status"] == "ok" for check in checks.values()) else "degraded"
        return {"status": overall_status, "service": settings.app_name, "checks": checks}

    if settings.enable_otel:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    return app


app = create_app()
