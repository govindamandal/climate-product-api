from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from uuid import uuid4

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.db.base import Base
from app.db.schema_guard import ensure_runtime_columns
from app.db.session import engine
from app.observability.logging import configure_logging

configure_logging()
settings = get_settings()


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid4()))
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response


def create_app() -> FastAPI:
    Base.metadata.create_all(bind=engine)
    ensure_runtime_columns(engine)
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Multi-tenant climate product management API with DPP and AI workflows.",
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.get("/health", tags=["System"])
    def health() -> dict:
        return {"status": "ok", "service": settings.app_name}

    if settings.enable_otel:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    return app


app = create_app()
