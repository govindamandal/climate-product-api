import json
import logging
from functools import cached_property
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self) -> None:
        self.settings = get_settings()

    @cached_property
    def client(self) -> Redis:
        return Redis.from_url(self.settings.redis_url, decode_responses=True)

    def get_json(self, key: str) -> dict[str, Any] | None:
        try:
            raw = self.client.get(key)
        except RedisError as exc:
            logger.warning("cache_read_failed", extra={"key": key, "error": str(exc)})
            return None
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("cache_decode_failed", extra={"key": key})
            return None

    def set_json(self, key: str, value: dict[str, Any], *, ttl_seconds: int) -> None:
        try:
            self.client.set(key, json.dumps(value), ex=ttl_seconds)
        except (RedisError, TypeError) as exc:
            logger.warning("cache_write_failed", extra={"key": key, "error": str(exc)})

    def delete(self, key: str) -> None:
        try:
            self.client.delete(key)
        except RedisError as exc:
            logger.warning("cache_delete_failed", extra={"key": key, "error": str(exc)})

    def ping(self) -> bool:
        try:
            return bool(self.client.ping())
        except RedisError as exc:
            logger.warning("cache_ping_failed", extra={"error": str(exc)})
            return False


def analytics_cache_key(organization_id: str) -> str:
    return f"analytics:summary:{organization_id}"
