from functools import lru_cache
import json
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Climate Product Platform API"
    environment: str = "local"
    database_url: str = "sqlite:///./climate.sqlite3"
    redis_url: str = "redis://localhost:6379/0"
    analytics_cache_ttl_seconds: int = 120
    jwt_secret_key: str = Field(default="dev-only-secret")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    password_reset_token_expire_minutes: int = 30
    frontend_base_url: str = "http://localhost:5173"
    cors_origins: str | list[str] = "http://localhost:5173,http://127.0.0.1:5173"
    max_request_body_bytes: int = 10 * 1024 * 1024
    auth_rate_limit_per_minute: int = 120
    email_provider: str = "local"
    resend_api_key: str | None = None
    email_from: str = "Material Passport OS <onboarding@example.com>"
    enable_otel: bool = False
    ai_provider: str = "local"
    ai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str | None = None
    anthropic_model: str = "claude-3-5-sonnet-latest"
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    anthropic_api_key: str | None = None
    cloudflare_r2_account_id: str | None = None
    cloudflare_r2_access_key_id: str | None = None
    cloudflare_r2_secret_access_key: str | None = None
    cloudflare_r2_bucket: str | None = None
    cloudflare_r2_public_base_url: str | None = None
    cloudflare_r2_public_url: str | None = None
    cloudflare_r2_endpoint_url: str | None = None
    max_product_image_bytes: int = 5 * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        if isinstance(self.cors_origins, list):
            origins = self.cors_origins
        else:
            value = self.cors_origins.strip().strip("'\"")
            if value.startswith("CORS_ORIGINS="):
                value = value.removeprefix("CORS_ORIGINS=").strip().strip("'\"")
            if not value:
                return self._default_cors_origins()
            if value.startswith("["):
                parsed = json.loads(value)
                origins = [str(item).strip() for item in parsed if str(item).strip()]
            else:
                origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        return self._normalize_origins([*origins, *self._default_cors_origins()])

    @property
    def sqlalchemy_database_url(self) -> str:
        database_url = self._normalize_database_url(self.database_url)
        if database_url.startswith("postgresql://"):
            return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        if database_url.startswith("postgres://"):
            return database_url.replace("postgres://", "postgresql+psycopg://", 1)
        return database_url

    def _default_cors_origins(self) -> list[str]:
        return [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "https://climate-product-web.vercel.app",
        ]

    def _normalize_origins(self, origins: list[str]) -> list[str]:
        normalized: list[str] = []
        for origin in origins:
            clean_origin = origin.strip().strip("'\"").rstrip("/")
            if clean_origin and clean_origin not in normalized:
                normalized.append(clean_origin)
        return normalized

    def _normalize_database_url(self, database_url: str) -> str:
        clean_url = database_url.strip().strip("'\"")
        if clean_url.startswith("DATABASE_URL="):
            clean_url = clean_url.removeprefix("DATABASE_URL=").strip().strip("'\"")
        parts = urlsplit(clean_url)
        if not parts.query:
            return clean_url
        query = urlencode(
            [(key.strip(), value.strip()) for key, value in parse_qsl(parts.query, keep_blank_values=True)]
        )
        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


@lru_cache
def get_settings() -> Settings:
    return Settings()
