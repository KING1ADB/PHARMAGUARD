import json
import logging
import time
from typing import Optional, Any

from ...core.config import settings

logger = logging.getLogger("pharmaguard.gcp.redis")

class MemorystoreRedisService:
    """
    Production Redis service for Google Cloud Memorystore.
    Provides distributed caching, rate-limiting counters, and distributed
    concurrency locks to coordinate autonomous agents across multiple Cloud Run replicas.
    """

    def __init__(self):
        self._client = None
        self._in_memory_store: dict = {}
        self._locks: dict = {}
        self.use_fallback = False

        try:
            import redis
            if settings.REDIS_URL:
                self._client = redis.from_url(
                    settings.REDIS_URL,
                    socket_connect_timeout=3,
                    socket_timeout=3,
                    decode_responses=True
                )
            else:
                self._client = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    password=settings.REDIS_PASSWORD,
                    socket_connect_timeout=3,
                    socket_timeout=3,
                    decode_responses=True
                )
            # Test ping
            self._client.ping()
            logger.info("Successfully connected to Google Cloud Memorystore / Redis.")
        except Exception as e:
            logger.warning(f"Redis Memorystore connection not available, using in-memory store fallback: {e}")
            self._client = None
            self.use_fallback = True

    def set(self, key: str, value: Any, expire_seconds: Optional[int] = None) -> bool:
        """Sets a key-value pair with optional TTL."""
        serialized = json.dumps(value) if not isinstance(value, str) else value
        if not self.use_fallback and self._client:
            try:
                self._client.set(key, serialized, ex=expire_seconds)
                return True
            except Exception as e:
                logger.error(f"Redis set error: {e}")

        # In-memory fallback
        self._in_memory_store[key] = {
            "value": serialized,
            "expiry": time.time() + expire_seconds if expire_seconds else None
        }
        return True

    def get(self, key: str) -> Optional[Any]:
        """Gets a value by key."""
        if not self.use_fallback and self._client:
            try:
                val = self._client.get(key)
                if val is not None:
                    try:
                        return json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        return val
                return None
            except Exception as e:
                logger.error(f"Redis get error: {e}")

        # In-memory fallback
        item = self._in_memory_store.get(key)
        if not item:
            return None
        if item["expiry"] and time.time() > item["expiry"]:
            del self._in_memory_store[key]
            return None
        try:
            return json.loads(item["value"])
        except (json.JSONDecodeError, TypeError):
            return item["value"]

    def acquire_distributed_lock(self, lock_name: str, lock_timeout_seconds: int = 60) -> bool:
        """
        Acquires a distributed lock to prevent duplicate morning agent runs across Cloud Run instances.
        Returns True if lock acquired, False if already held.
        """
        key = f"lock:agent:{lock_name}"
        if not self.use_fallback and self._client:
            try:
                acquired = self._client.set(key, "LOCKED", nx=True, ex=lock_timeout_seconds)
                return bool(acquired)
            except Exception as e:
                logger.error(f"Redis lock error: {e}")

        # In-memory fallback
        now = time.time()
        if key in self._locks:
            if now < self._locks[key]:
                return False  # Still locked
        self._locks[key] = now + lock_timeout_seconds
        return True

    def release_distributed_lock(self, lock_name: str) -> bool:
        """Releases a distributed lock."""
        key = f"lock:agent:{lock_name}"
        if not self.use_fallback and self._client:
            try:
                self._client.delete(key)
                return True
            except Exception as e:
                logger.error(f"Redis release lock error: {e}")

        if key in self._locks:
            del self._locks[key]
        return True

    def check_health(self) -> dict:
        """Checks Redis health status."""
        if not self.use_fallback and self._client:
            try:
                self._client.ping()
                info = self._client.info(section="server")
                return {
                    "healthy": True,
                    "provider": "GOOGLE_CLOUD_MEMORYSTORE_REDIS",
                    "version": info.get("redis_version", "unknown"),
                    "connected_clients": info.get("connected_clients", 1)
                }
            except Exception as e:
                return {
                    "healthy": False,
                    "provider": "GOOGLE_CLOUD_MEMORYSTORE_REDIS",
                    "error": str(e)
                }
        return {
            "healthy": True,
            "provider": "IN_MEMORY_CACHE_EMULATOR",
            "active_keys": len(self._in_memory_store),
            "mode": "STANDBY_FALLBACK"
        }


redis_service = MemorystoreRedisService()
