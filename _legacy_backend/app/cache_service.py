"""Redis-backed JSON cache used by dashboard and external API endpoints.

Redis is an optimization, not the source of truth. Cache failures are logged
and requests continue against PostgreSQL or the external provider.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import date, datetime
from typing import Any

import redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Value of type {type(value).__name__} is not JSON serializable")


class RedisJsonCache:
    def __init__(
        self,
        redis_url: str | None = None,
        *,
        client: redis.Redis | None = None,
    ) -> None:
        self.enabled = os.getenv("CACHE_ENABLED", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.key_prefix = os.getenv("CACHE_KEY_PREFIX", "gbtac:v1").strip().strip(":")
        self.redis_url = (
            redis_url
            or os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0").strip()
        )
        self.connect_timeout = max(
            0.2,
            float(os.getenv("REDIS_CONNECT_TIMEOUT_SECONDS", "1.5")),
        )
        self.socket_timeout = max(
            0.2,
            float(os.getenv("REDIS_SOCKET_TIMEOUT_SECONDS", "1.5")),
        )

        self._client = client
        if self._client is None and self.enabled:
            self._client = redis.Redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=self.connect_timeout,
                socket_timeout=self.socket_timeout,
                health_check_interval=30,
                retry_on_timeout=True,
            )

    def namespaced_key(self, key: str) -> str:
        normalized = key.strip().lstrip(":")
        return f"{self.key_prefix}:{normalized}"

    def parameter_key(self, namespace: str, **parameters: Any) -> str:
        canonical = json.dumps(
            parameters,
            sort_keys=True,
            separators=(",", ":"),
            default=_json_default,
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
        return self.namespaced_key(f"{namespace}:{digest}")

    def get_json(self, key: str, *, namespaced: bool = True) -> Any | None:
        if not self.enabled or self._client is None:
            return None

        full_key = self.namespaced_key(key) if namespaced else key
        try:
            raw_value = self._client.get(full_key)
            if raw_value is None:
                return None
            return json.loads(raw_value)
        except (RedisError, json.JSONDecodeError) as error:
            logger.warning("Redis cache read failed for %s: %s", full_key, error)
            return None

    def set_json(
        self,
        key: str,
        value: Any,
        ttl_seconds: int,
        *,
        namespaced: bool = True,
    ) -> bool:
        if not self.enabled or self._client is None:
            return False

        full_key = self.namespaced_key(key) if namespaced else key
        ttl_seconds = max(1, int(ttl_seconds))
        try:
            serialized = json.dumps(
                value,
                separators=(",", ":"),
                default=_json_default,
            )
            self._client.set(full_key, serialized, ex=ttl_seconds)
            return True
        except (RedisError, TypeError, ValueError) as error:
            logger.warning("Redis cache write failed for %s: %s", full_key, error)
            return False

    def delete(self, key: str, *, namespaced: bool = True) -> bool:
        if not self.enabled or self._client is None:
            return False

        full_key = self.namespaced_key(key) if namespaced else key
        try:
            self._client.delete(full_key)
            return True
        except RedisError as error:
            logger.warning("Redis cache delete failed for %s: %s", full_key, error)
            return False

    def clear_namespace(self) -> int:
        """Delete only keys belonging to this application cache prefix."""
        if not self.enabled or self._client is None:
            return 0

        deleted = 0
        pattern = self.namespaced_key("*")
        try:
            for key in self._client.scan_iter(match=pattern, count=200):
                deleted += int(self._client.delete(key))
            return deleted
        except RedisError as error:
            logger.warning("Redis namespace clear failed: %s", error)
            return 0

    def ping(self) -> bool:
        if not self.enabled or self._client is None:
            return False
        try:
            return bool(self._client.ping())
        except RedisError:
            return False

    def ttl(self, key: str, *, namespaced: bool = True) -> int | None:
        if not self.enabled or self._client is None:
            return None
        full_key = self.namespaced_key(key) if namespaced else key
        try:
            value = int(self._client.ttl(full_key))
            return value if value >= 0 else None
        except RedisError:
            return None


cache = RedisJsonCache()
