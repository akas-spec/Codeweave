import time
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.llm_usage import LLMUsage

logger = logging.getLogger(__name__)

# Cost table: model -> (input_cost_per_token, output_cost_per_token) in USD
COST_TABLE: dict[str, tuple[float, float]] = {
    # Free tier — $0
    "nvidia/llama-3.1-nemotron-70b-instruct:free": (0.0, 0.0),
    "nvidia/nemotron-3-ultra-253b-v1:free": (0.0, 0.0),
    # Paid tiers
    "nvidia/llama-3.1-nemotron-70b-instruct": (0.0000005, 0.0000022),  # $0.50/$2.20 per 1M
    # OpenAI reference (if switched)
    "openai/gpt-4o": (0.0000025, 0.00001),
    "openai/gpt-4o-mini": (0.00000015, 0.0000006),
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate USD cost for an LLM call."""
    rates = COST_TABLE.get(model, (0.0, 0.0))
    return round(rates[0] * input_tokens + rates[1] * output_tokens, 8)


class CostTracker:
    """Records LLM usage (tokens, cost, latency) to the llm_usage table."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def record(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        endpoint: str = "chat",
        user_id: Optional[int] = None,
        latency_ms: Optional[int] = None,
        success: bool = True,
    ) -> LLMUsage:
        """Insert a usage record. Safe to call even if tokens are 0."""
        cost = calculate_cost(model, input_tokens, output_tokens)
        record = LLMUsage(
            user_id=user_id,
            model=model,
            endpoint=endpoint,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
            success=1 if success else 0,
        )
        try:
            self._db.add(record)
            await self._db.flush()
            logger.info(
                "LLM usage: model=%s in=%d out=%d cost=$%.6f latency=%sms",
                model, input_tokens, output_tokens, cost,
                latency_ms if latency_ms is not None else "?",
            )
        except Exception as e:
            logger.warning("Failed to record LLM usage: %s", e)
        return record


class TimedLLMCall:
    """Context manager that times an LLM call and records usage on exit.

    Usage:
        async with TimedLLMCall(tracker, model="...", endpoint="chat") as t:
            response = await llm.chat(messages)
            t.set_usage(response.usage)
    """

    def __init__(
        self,
        tracker: CostTracker,
        model: str,
        endpoint: str = "chat",
        user_id: Optional[int] = None,
    ):
        self._tracker = tracker
        self._model = model
        self._endpoint = endpoint
        self._user_id = user_id
        self._start: float = 0.0
        self._usage: dict = {}
        self._success = True

    async def __aenter__(self):
        self._start = time.monotonic()
        return self

    def set_usage(self, usage: Optional[dict]):
        """Call inside the context with the LLM response usage dict."""
        if usage:
            self._usage = usage

    def mark_failure(self):
        self._success = False

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self._success = False
        latency_ms = int((time.monotonic() - self._start) * 1000)
        await self._tracker.record(
            model=self._model,
            input_tokens=self._usage.get("prompt_tokens", 0),
            output_tokens=self._usage.get("completion_tokens", 0),
            endpoint=self._endpoint,
            user_id=self._user_id,
            latency_ms=latency_ms,
            success=self._success,
        )
        return False  # Don't suppress exceptions
