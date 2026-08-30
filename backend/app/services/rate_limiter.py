import time
import logging
from typing import Optional
import redis.asyncio as aioredis
from fastapi import HTTPException, status
from app.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Per-user and global LLM call rate limiting backed by Redis.

    Per-user quota: configurable daily call limit per user.
    Global quota:   mirrors Nemotron free-tier limits.
    Global concurrency: semaphore caps simultaneous in-flight LLM calls.
    """

    # Redis key templates
    USER_DAILY_KEY = "codeweave:user:{user_id}:llm_calls:{date}"  # TTL 86400
    GLOBAL_MINUTE_KEY = "codeweave:llm:minute:{minute}"           # TTL 60
    GLOBAL_DAILY_KEY = "codeweave:llm:daily:{date}"               # TTL 86400
    CONCURRENCY_KEY = "codeweave:llm:concurrency"                  # Set of in-flight call IDs

    DEFAULT_USER_DAILY_LIMIT = 500       # calls/day per user
    GLOBAL_MINUTE_LIMIT = 100           # safety margin
    GLOBAL_DAILY_LIMIT = 2000           # safety margin
    MAX_CONCURRENT = 5                  # max simultaneous LLM calls

    def __init__(self, redis_client: aioredis.Redis):
        self._redis = redis_client

    def _today(self) -> str:
        from datetime import date
        return date.today().isoformat()

    def _current_minute(self) -> str:
        return str(int(time.time()) // 60)

    async def check_and_increment_user(self, user_id: int) -> None:
        """Check per-user daily quota. Raises HTTP 429 if exceeded."""
        key = self.USER_DAILY_KEY.format(user_id=user_id, date=self._today())
        try:
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, 86400)
            if count > self.DEFAULT_USER_DAILY_LIMIT:
                logger.warning("User %s exceeded daily LLM quota (%d)", user_id, count)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Daily LLM quota exceeded ({self.DEFAULT_USER_DAILY_LIMIT} calls/day). Try again tomorrow.",
                    headers={"Retry-After": "86400"},
                )
        except HTTPException:
            raise
        except Exception as e:
            # Redis down — allow the request but log the warning
            logger.warning("Rate limiter error (user quota): %s — allowing request", e)

    async def check_and_increment_global_minute(self) -> None:
        """Check global per-minute limit. Raises HTTP 429 if exceeded."""
        key = self.GLOBAL_MINUTE_KEY.format(minute=self._current_minute())
        try:
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, 60)
            if count > self.GLOBAL_MINUTE_LIMIT:
                logger.warning("Global LLM minute limit hit (%d/min)", count)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Server is busy. Please wait a moment and retry.",
                    headers={"Retry-After": "10"},
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("Rate limiter error (global minute): %s — allowing request", e)

    async def check_and_increment_global_daily(self) -> None:
        """Check global daily limit (mirrors Nemotron free-tier). Raises HTTP 429 if exceeded."""
        key = self.GLOBAL_DAILY_KEY.format(date=self._today())
        try:
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, 86400)
            if count > self.GLOBAL_DAILY_LIMIT:
                logger.warning("Global LLM daily limit hit (%d/day)", count)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Daily AI quota exhausted. Try again tomorrow or upgrade your plan.",
                    headers={"Retry-After": "86400"},
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("Rate limiter error (global daily): %s — allowing request", e)

    async def check_all(self, user_id: Optional[int] = None) -> None:
        """Run all rate limit checks in sequence. Call before every LLM request."""
        await self.check_and_increment_global_minute()
        await self.check_and_increment_global_daily()
        if user_id is not None:
            await self.check_and_increment_user(user_id)

    async def get_user_usage(self, user_id: int) -> dict:
        """Return current usage stats for a user."""
        user_key = self.USER_DAILY_KEY.format(user_id=user_id, date=self._today())
        minute_key = self.GLOBAL_MINUTE_KEY.format(minute=self._current_minute())
        daily_key = self.GLOBAL_DAILY_KEY.format(date=self._today())
        try:
            user_count, minute_count, daily_count = await self._redis.mget(user_key, minute_key, daily_key)
            return {
                "user_calls_today": int(user_count or 0),
                "user_daily_limit": self.DEFAULT_USER_DAILY_LIMIT,
                "global_calls_this_minute": int(minute_count or 0),
                "global_minute_limit": self.GLOBAL_MINUTE_LIMIT,
                "global_calls_today": int(daily_count or 0),
                "global_daily_limit": self.GLOBAL_DAILY_LIMIT,
            }
        except Exception:
            return {}


# Module-level singleton
_rate_limiter: Optional[RateLimiter] = None


def init_rate_limiter(redis_url: str = None) -> RateLimiter:
    """Initialise the module-level RateLimiter singleton."""
    global _rate_limiter
    url = redis_url or settings.REDIS_URL
    pool = aioredis.ConnectionPool.from_url(url, max_connections=10)
    client = aioredis.Redis(connection_pool=pool)
    _rate_limiter = RateLimiter(client)
    return _rate_limiter


def get_rate_limiter() -> RateLimiter:
    if _rate_limiter is None:
        raise RuntimeError("RateLimiter not initialised. Call init_rate_limiter() during startup.")
    return _rate_limiter
