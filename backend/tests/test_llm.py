import pytest
from app.services.llm.base import ChatMessage, LLMResponse, get_llm_provider
from app.services.llm.local import LocalLLMProvider


def test_chat_message_creation():
    msg = ChatMessage(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_llm_response_creation():
    resp = LLMResponse(content="Hi there", model="test-model")
    assert resp.content == "Hi there"
    assert resp.model == "test-model"
    assert resp.usage is None


def test_get_llm_provider_nemotron():
    provider = get_llm_provider("nemotron")
    assert provider is not None


def test_get_llm_provider_local():
    provider = get_llm_provider("local")
    assert isinstance(provider, LocalLLMProvider)


def test_get_llm_provider_invalid():
    with pytest.raises(ValueError):
        get_llm_provider("nonexistent")


@pytest.mark.asyncio
async def test_local_provider_chat():
    provider = LocalLLMProvider()
    msg = ChatMessage(role="user", content="Hello")
    response = await provider.chat([msg])
    assert response.content is not None
    assert response.model == "mistral"


@pytest.mark.asyncio
async def test_local_provider_health():
    provider = LocalLLMProvider()
    healthy = await provider.health_check()
    assert healthy is False  # Not implemented yet
