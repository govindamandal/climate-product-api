from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Climate Product Platform API"
    environment: str = "local"
    database_url: str = "sqlite:///./climate.sqlite3"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str = Field(default="dev-only-secret")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    enable_otel: bool = False
    ai_provider: str = "local"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    cloudflare_r2_account_id: str | None = None
    cloudflare_r2_access_key_id: str | None = None
    cloudflare_r2_secret_access_key: str | None = None
    cloudflare_r2_bucket: str | None = None
    cloudflare_r2_public_base_url: str | None = None
    cloudflare_r2_endpoint_url: str | None = None
    max_product_image_bytes: int = 5 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
