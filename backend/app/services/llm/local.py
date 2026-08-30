import logging
from typing import Optional
from app.services.llm.base import LLMProvider, ChatMessage, LLMResponse

logger = logging.getLogger(__name__)

class LocalLLMProvider(LLMProvider):
    """Stub for a local LLM provider (e.g., Ollama, vLLM).
    
    This is a placeholder that returns a message indicating
    local LLM is not yet configured. Implement when needed.
    """

    def __init__(self, model_name: str = "mistral", base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url

    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Placeholder: local LLM not yet implemented."""
        logger.warning("Local LLM provider called but not yet implemented.")
        return LLMResponse(
            content="[Local LLM not configured. Please set up Ollama or another local provider.]",
            model=self.model_name,
            usage=None,
            finish_reason="stop",
        )

    async def health_check(self) -> bool:
        """Check if local LLM server is running."""
        return False  # Not implemented yet
