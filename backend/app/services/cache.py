import json
import hashlib
import logging
from typing import Optional, Any
import redis.asyncio as aioredis
from app.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Redis-backed caching for LLM responses and embeddings.
    
    Uses Redis DB=0 with LRU eviction for cache entries.
    - LLM response cache: TTL 1 hour
    - Embedding cache: TTL 24 hours
    """

    # Key prefixes
    LLM_PREFIX = "codeweave:llm:cache:"
    EMBED_PREFIX = "codeweave:embed:"

    # TTLs
    LLM_TTL = 3600        # 1 hour
    EMBED_TTL = 86400     # 24 hours

    def __init__(self, redis_client: aioredis.Redis):
        self._redis = redis_client

    @staticmethod
    def _make_key(prefix: str, *parts: str) -> str:
        """Create a deterministic cache key by hashing the parts."""
        raw = "|".join(str(p) for p in parts)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        return f"{prefix}{digest}"

    # ── LLM response cache ──────────────────────────────────────────────────

    async def get_llm_response(self, question: str, repo_id: int) -> Optional[dict]:
        """Return cached LLM response or None."""
        key = self._make_key(self.LLM_PREFIX, question, str(repo_id))
        try:
            raw = await self._redis.get(key)
            if raw:
                logger.debug("LLM cache HIT for repo %s", repo_id)
                return json.loads(raw)
        except Exception as e:
            logger.warning("Cache GET error (LLM): %s", e)
        return None

    async def set_llm_response(self, question: str, repo_id: int, response: dict) -> None:
        """Cache an LLM response."""
        key = self._make_key(self.LLM_PREFIX, question, str(repo_id))
        try:
            await self._redis.set(key, json.dumps(response), ex=self.LLM_TTL)
            logger.debug("LLM cache SET for repo %s (TTL=%ds)", repo_id, self.LLM_TTL)
        except Exception as e:
            logger.warning("Cache SET error (LLM): %s", e)

    async def invalidate_repo_cache(self, repo_id: int) -> None:
        """Invalidate all cached responses for a repository (e.g. after re-ingestion)."""
        # Scan and delete matching keys — acceptable for small caches
        pattern = f"{self.LLM_PREFIX}*"
        try:
            async for key in self._redis.scan_iter(pattern):
                await self._redis.delete(key)
        except Exception as e:
            logger.warning("Cache invalidation error: %s", e)

    # ── Embedding cache ─────────────────────────────────────────────────────

    async def get_embedding(self, text: str) -> Optional[list[float]]:
        """Return cached embedding vector or None."""
        key = self._make_key(self.EMBED_PREFIX, text)
        try:
            raw = await self._redis.get(key)
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.warning("Cache GET error (embed): %s", e)
        return None

    async def set_embedding(self, text: str, embedding: list[float]) -> None:
        """Cache an embedding vector."""
        key = self._make_key(self.EMBED_PREFIX, text)
        try:
            await self._redis.set(key, json.dumps(embedding), ex=self.EMBED_TTL)
        except Exception as e:
            logger.warning("Cache SET error (embed): %s", e)

    # ── Health ───────────────────────────────────────────────────────────────

    async def ping(self) -> bool:
        """Return True if Redis is reachable."""
        try:
            return await self._redis.ping()
        except Exception:
            return False


# Module-level singleton — created during FastAPI lifespan startup
_cache_service: Optional[CacheService] = None


def init_cache(redis_url: str = None) -> CacheService:
    """Initialise the module-level CacheService singleton."""
    global _cache_service
    url = redis_url or settings.REDIS_URL
    # DB=0 for cache (LRU eviction configured in Redis)
    pool = aioredis.ConnectionPool.from_url(url + "/0" if not url.endswith("/0") else url, max_connections=20)
    client = aioredis.Redis(connection_pool=pool)
    _cache_service = CacheService(client)
    return _cache_service


def get_cache() -> CacheService:
    """Return the module-level CacheService. Call init_cache() first."""
    if _cache_service is None:
        raise RuntimeError("CacheService not initialised. Call init_cache() during startup.")
    return _cache_service
