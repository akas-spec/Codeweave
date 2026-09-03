"""Shared pytest fixtures for CodeWeave backend tests.

Provides:
  - Mock EmbeddingService (avoids downloading the 90 MB model)
  - Mock LLMProvider    (avoids hitting OpenRouter in CI)
  - In-memory / isolated async DB sessions when needed
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Mock Embedding Service
# ---------------------------------------------------------------------------

EMBEDDING_DIM = 384


class MockEmbeddingService:
    """Drop-in replacement for EmbeddingService that returns deterministic vectors."""

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def encode(self, text: str) -> list[float]:
        """Return a deterministic vector based on the hash of the input text."""
        h = hash(text) % 1000
        base = [h / 1000.0] * EMBEDDING_DIM
        return base

    async def aencode(self, text: str) -> list[float]:
        return self.encode(text)

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.encode(t) for t in texts]


# ---------------------------------------------------------------------------
# Mock LLM Provider
# ---------------------------------------------------------------------------

@dataclass
class MockLLMResponse:
    content: str
    model: str = "mock-model"
    usage: dict = None


class MockLLMProvider:
    """Mock LLM provider that returns canned responses."""

    def __init__(self, responses: list[str] | None = None):
        self._responses = responses or ["This is a mock LLM response."]
        self._call_count = 0

    async def chat(self, messages, **kwargs):
        idx = min(self._call_count, len(self._responses) - 1)
        self._call_count += 1
        return MockLLMResponse(content=self._responses[idx])

    async def chat_stream(self, messages, **kwargs):
        response = self._responses[min(self._call_count, len(self._responses) - 1)]
        self._call_count += 1
        for word in response.split():
            yield word + " "

    async def health_check(self):
        return True


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_embedding_service():
    """Fixture that patches EmbeddingService.get_instance globally."""
    svc = MockEmbeddingService()
    with patch("app.services.embeddings.EmbeddingService.get_instance", return_value=svc):
        yield svc


@pytest.fixture
def mock_llm_provider():
    """Fixture providing a MockLLMProvider instance."""
    return MockLLMProvider()


@pytest.fixture
def mock_llm_provider_factory():
    """Fixture providing a factory to create MockLLMProvider with custom responses."""
    def _factory(responses: list[str]):
        return MockLLMProvider(responses=responses)
    return _factory
