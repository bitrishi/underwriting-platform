"""Persistence layer for underwriting API evaluation history."""

from __future__ import annotations

from collections import defaultdict
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class EvaluationHistoryStore:
    """Store evaluation history in Redis, with in-memory fallback for local use."""

    def __init__(self, redis_url: str | None = None):
        self.redis_url = (redis_url or "").strip()
        self._redis: Any | None = None
        self._memory: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._connect()

    def _connect(self) -> None:
        if not self.redis_url:
            logger.info("Evaluation history store using in-memory mode; REDIS_URL not configured.")
            return

        try:
            import redis  # type: ignore[import]

            client = redis.from_url(self.redis_url, decode_responses=True)
            client.ping()
            self._redis = client
            logger.info("Evaluation history store connected to Redis.")
        except Exception as exc:
            logger.warning("Redis unavailable, falling back to in-memory history: %s", exc)
            self._redis = None

    def append(self, application_id: str, record: dict[str, Any]) -> None:
        if self._redis is not None:
            try:
                self._redis.lpush(self._key(application_id), json.dumps(record))
                self._redis.ltrim(self._key(application_id), 0, 99)
                return
            except Exception as exc:
                logger.warning("Redis write failed, using in-memory fallback: %s", exc)

        self._memory[application_id].insert(0, record)
        self._memory[application_id] = self._memory[application_id][:100]

    def get_history(self, application_id: str) -> list[dict[str, Any]]:
        if self._redis is not None:
            try:
                raw_items = self._redis.lrange(self._key(application_id), 0, -1)
                return [json.loads(item) for item in raw_items]
            except Exception as exc:
                logger.warning("Redis read failed, using in-memory fallback: %s", exc)

        return list(self._memory.get(application_id, []))

    @staticmethod
    def _key(application_id: str) -> str:
        return f"evaluation_history:{application_id}"
