import httpx
import asyncio
import logging
from typing import Optional
from app.config import settings
from app.services.llm.base import LLMProvider, ChatMessage, LLMResponse

logger = logging.getLogger(__name__)

class NemotronProvider(LLMProvider):
    """LLM Provider using NVIDIA Nemotron via OpenRouter (free tier)."""

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.base_url = settings.OPENROUTER_BASE_URL
        self.model = settings.DEFAULT_MODEL
        self.max_retries = 3
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=10.0),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://codeweave.dev",
                "X-Title": "CodeWeave",
            },
        )

    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Send chat completion to OpenRouter with exponential backoff retry."""
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await self.client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                )

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 2 ** (attempt + 1)))
                    logger.warning(f"Rate limited. Retrying after {retry_after}s (attempt {attempt + 1})")
                    await asyncio.sleep(retry_after)
                    continue

                response.raise_for_status()
                data = response.json()

                if "error" in data:
                    logger.error(f"OpenRouter returned error in 200 OK response: {data['error']}")
                    raise RuntimeError(f"OpenRouter API Error: {data['error'].get('message', data['error'])}")

                choice = data["choices"][0]
                return LLMResponse(
                    content=choice["message"]["content"],
                    model=data.get("model", self.model),
                    usage=data.get("usage"),
                    finish_reason=choice.get("finish_reason"),
                )

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
                if e.response.status_code >= 500:
                    await asyncio.sleep(2 ** (attempt + 1))
                    continue
                raise
            except httpx.RequestError as e:
                last_error = e
                logger.error(f"Request error: {e}")
                await asyncio.sleep(2 ** (attempt + 1))
                continue

        raise RuntimeError(f"Failed after {self.max_retries} retries: {last_error}")

    async def health_check(self) -> bool:
        """Check if OpenRouter is reachable."""
        try:
            response = await self.client.get(f"{self.base_url}/models")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
