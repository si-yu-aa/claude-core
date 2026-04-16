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

@pytest.mark.asyncio
async def test_client_strips_trailing_slash():
    client = LLMClient(
        base_url="https://api.openai.com/v1/",
        api_key="test-key"
    )
    assert client.base_url == "https://api.openai.com/v1"
    assert not client.base_url.endswith("/")

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