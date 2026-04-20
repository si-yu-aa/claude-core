import pytest
from claude_core.api.client import LLMClient
from claude_core.api.errors import APIError, RateLimitError

@pytest.mark.asyncio
async def test_client_initialization():
    client = LLMClient(
        base_url="https://api.openai.com/v1",
        api_key="test-key",
        model="gpt-4o"
    )
    assert client.base_url == "https://api.openai.com/v1"
    assert client.model == "gpt-4o"
    assert client.provider_name == "openai"

@pytest.mark.asyncio
async def test_client_strips_trailing_slash():
    client = LLMClient(
        base_url="https://api.openai.com/v1/",
        api_key="test-key"
    )
    assert client.base_url == "https://api.openai.com/v1"
    assert not client.base_url.endswith("/")


@pytest.mark.asyncio
async def test_client_uses_provider_default_base_url():
    client = LLMClient(
        base_url=None,
        api_key="test-key",
        provider="gemini",
    )
    assert "generativelanguage.googleapis.com" in client.base_url
    assert client.provider_name == "gemini"


@pytest.mark.asyncio
async def test_client_builds_provider_specific_url():
    client = LLMClient(
        base_url=None,
        api_key="test-key",
        provider="gemini",
    )
    assert client._build_chat_completions_url().endswith("/chat/completions")

def test_api_error_class():
    error = APIError(
        message="Invalid request",
        status_code=400,
        body={"error": "bad request"}
    )
    assert error.message == "Invalid request"
    assert error.status_code == 400

def test_rate_limit_error():
    error = RateLimitError(
        message="Rate limit exceeded",
        retry_after=60
    )
    assert "rate limit" in error.message.lower()
    assert error.retry_after == 60
