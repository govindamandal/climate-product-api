from time import perf_counter
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from uuid import uuid4

from app.api.v1.router import api_router
from app.api.deps import DbSession
from app.core.config import get_settings
from app.core.middleware import (
    AuthRateLimitMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.observability.logging import configure_logging
from app.services.operations_service import OperationsService

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
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware, max_body_bytes=settings.max_request_body_bytes)
    app.add_middleware(AuthRateLimitMiddleware, requests_per_minute=settings.auth_rate_limit_per_minute)
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
        status = OperationsService(db).status()
        return status.model_dump(mode="json")

    if settings.enable_otel:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    return app


app = create_app()
