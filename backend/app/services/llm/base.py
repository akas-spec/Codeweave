from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class ChatMessage:
    role: str  # 'system', 'user', 'assistant'
    content: str

@dataclass
class LLMResponse:
    content: str
    model: str
    usage: Optional[dict] = None
    finish_reason: Optional[str] = None

class LLMProvider(ABC):
    """Abstract base class for LLM providers. Enables provider-agnostic LLM usage."""

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Send a chat completion request."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available."""
        ...

def get_llm_provider(provider_name: str = "nemotron") -> LLMProvider:
    """Factory function to get an LLM provider instance."""
    if provider_name == "nemotron":
        from app.services.llm.nemotron import NemotronProvider
        return NemotronProvider()
    elif provider_name == "local":
        from app.services.llm.local import LocalLLMProvider
        return LocalLLMProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {provider_name}")
