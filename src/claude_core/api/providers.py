"""API Provider abstraction layer.

This module provides a provider interface that allows QueryEngine
to work with different LLM backends (OpenAI-compatible, Anthropic, etc.)
without direct dependency on specific client implementations.
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncGenerator

from claude_core.api.errors import APIError, RateLimitError, AuthenticationError, InvalidRequestError, APIConnectionError, is_retryable_error


@dataclass
class ProviderConfig:
    """Configuration for an API provider."""
    base_url: str
    api_key: str
    model: str
    timeout: float = 120.0
    max_retries: int = 3
    initial_retry_delay: float = 1.0


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    Implement this interface to add support for different LLM backends.
    """

    @property
    @abstractmethod
    def config(self) -> ProviderConfig:
        """Get the provider configuration."""
        pass

    @property
    @abstractmethod
    def model(self) -> str:
        """Get the model name."""
        pass

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs: Any,
    ) -> dict:
        """
        Make a non-streaming chat completion request.

        Returns:
            Chat completion response dict
        """
        pass

    @abstractmethod
    async def chat_completion_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict, None]:
        """
        Make a streaming chat completion request.

        Yields:
            Stream events as dicts with keys like:
            - content_block_delta: delta content from streaming
            - tool_use: tool call from streaming
            - message_stop: end of message
            - usage: token usage information
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the provider and cleanup resources."""
        pass


class OpenAIProvider(LLMProvider):
    """
    OpenAI-compatible provider implementation.

    Supports any API that implements the OpenAI Chat Completions protocol,
    including Ollama, vLLM, DeepSeek, Azure OpenAI, etc.
    """

    def __init__(self, config: ProviderConfig):
        self._config = config
        self._client: Any | None = None

    @property
    def config(self) -> ProviderConfig:
        return self._config

    @property
    def model(self) -> str:
        return self._config.model

    def _build_headers(self) -> dict[str, str]:
        """Build request headers."""
        return {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }

    def _map_status_to_error(self, response: Any) -> APIError:
        """Map HTTP status code to appropriate error type."""
        status = response.status_code
        try:
            data = response.json()
            error_msg = data.get("error", {}).get("message", "") or data.get("message", "Unknown error")
        except Exception:
            error_msg = "Unknown error"

        if status == 401:
            return AuthenticationError(error_msg)
        elif status == 403:
            return AuthenticationError("Access forbidden")
        elif status == 400:
            return InvalidRequestError(error_msg, body=response.json() if response.content else None)
        elif status == 429:
            retry_after = response.headers.get("retry-after")
            return RateLimitError(error_msg, retry_after=int(retry_after) if retry_after else None)
        elif status >= 500:
            return APIConnectionError(f"Server error: {error_msg}")
        else:
            return APIError(f"HTTP {status}: {error_msg}", status_code=status)

    async def _get_client(self) -> Any:
        """Get or create the HTTP client."""
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(timeout=self._config.timeout)
        return self._client

    async def chat_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs: Any,
    ) -> dict:
        """Make a non-streaming chat completion request with retry logic."""
        client = await self._get_client()
        url = f"{self._config.base_url}/chat/completions"

        body: dict[str, Any] = {
            "model": self._config.model,
            "messages": messages,
            **kwargs,
        }
        if tools:
            body["tools"] = tools

        last_error: APIError | None = None
        retry_delay = self._config.initial_retry_delay

        for attempt in range(self._config.max_retries):
            try:
                response = await client.post(
                    url,
                    headers=self._build_headers(),
                    json=body,
                )

                if response.status_code != 200:
                    error = self._map_status_to_error(response)
                    last_error = error

                    if not is_retryable_error(error):
                        raise error

                    if attempt < self._config.max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        raise error

                return response.json()

            except APIError:
                raise
            except Exception as e:
                last_error = APIConnectionError(f"Connection error: {str(e)}")
                if attempt < self._config.max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                raise last_error

        raise last_error or APIError("Max retries exceeded")

    async def chat_completion_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict, None]:
        """Make a streaming chat completion request.

        Yields parsed SSE events including usage information.
        """
        client = await self._get_client()
        url = f"{self._config.base_url}/chat/completions"

        body: dict[str, Any] = {
            "model": self._config.model,
            "messages": messages,
            "stream": True,
            **kwargs,
        }
        if tools:
            body["tools"] = tools

        last_error: APIError | None = None
        retry_delay = self._config.initial_retry_delay

        for attempt in range(self._config.max_retries):
            try:
                async with client.stream(
                    "POST",
                    url,
                    headers=self._build_headers(),
                    json=body,
                ) as response:
                    if response.status_code != 200:
                        error = self._map_status_to_error(response)
                        last_error = error

                        if not is_retryable_error(error):
                            raise error

                        if attempt < self._config.max_retries - 1:
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                        else:
                            raise error

                    # Track usage from streaming response
                    prompt_tokens = 0
                    completion_tokens = 0
                    usage_recorded = False

                    # Buffer for streaming tool calls
                    buffered_tool_call: Any | None = None

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue

                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                # Yield any remaining buffered tool call
                                if buffered_tool_call and buffered_tool_call.id:
                                    try:
                                        yield {
                                            "type": "tool_use",
                                            "tool_use_id": buffered_tool_call.id,
                                            "name": buffered_tool_call.name,
                                            "input": json.loads(
                                                buffered_tool_call.arguments or "{}"
                                            ),
                                        }
                                    except json.JSONDecodeError:
                                        yield {
                                            "type": "tool_use",
                                            "tool_use_id": buffered_tool_call.id,
                                            "name": buffered_tool_call.name,
                                            "input": {},
                                        }
                                # Yield usage at end of stream
                                if not usage_recorded:
                                    yield {
                                        "type": "usage",
                                        "prompt_tokens": prompt_tokens,
                                        "completion_tokens": completion_tokens,
                                    }
                                yield {"type": "message_stop"}
                                break

                            try:
                                chunk = json.loads(data)
                            except json.JSONDecodeError:
                                continue

                            # Extract usage from chunk if available
                            if "usage" in chunk and not usage_recorded:
                                usage_data = chunk["usage"]
                                prompt_tokens = usage_data.get("prompt_tokens", 0)
                                completion_tokens = usage_data.get("completion_tokens", 0)
                                usage_recorded = True
                                yield {
                                    "type": "usage",
                                    "prompt_tokens": prompt_tokens,
                                    "completion_tokens": completion_tokens,
                                }

                            # Parse OpenAI chat completion chunk
                            if "choices" in chunk:
                                for choice in chunk["choices"]:
                                    delta = choice.get("delta", {})

                                    # Content delta
                                    if delta.get("content"):
                                        yield {
                                            "type": "content_block_delta",
                                            "index": choice.get("index", 0),
                                            "delta": {"content": delta["content"]},
                                        }

                                    # Tool use - buffer the streaming arguments
                                    if delta.get("tool_calls"):
                                        for tc in delta["tool_calls"]:
                                            if buffered_tool_call is None:
                                                buffered_tool_call = type(
                                                    "BufferedToolCall",
                                                    (),
                                                    {"id": "", "name": "", "arguments": ""}
                                                )()

                                            # Update tool call info
                                            if tc.get("id"):
                                                buffered_tool_call.id = tc["id"]
                                            if tc.get("function", {}).get("name"):
                                                buffered_tool_call.name = tc["function"]["name"]
                                            if tc.get("function", {}).get("arguments"):
                                                buffered_tool_call.arguments += tc["function"]["arguments"]

                                    # Finish reason
                                    if choice.get("finish_reason"):
                                        # Yield buffered tool call if present
                                        if buffered_tool_call and buffered_tool_call.id:
                                            try:
                                                yield {
                                                    "type": "tool_use",
                                                    "tool_use_id": buffered_tool_call.id,
                                                    "name": buffered_tool_call.name,
                                                    "input": json.loads(
                                                        buffered_tool_call.arguments or "{}"
                                                    ),
                                                }
                                            except json.JSONDecodeError:
                                                yield {
                                                    "type": "tool_use",
                                                    "tool_use_id": buffered_tool_call.id,
                                                    "name": buffered_tool_call.name,
                                                    "input": {},
                                                }
                                            buffered_tool_call = None

                                        yield {"type": "message_stop"}

                # Successfully streamed
                return

            except APIError:
                raise
            except Exception as e:
                last_error = APIConnectionError(f"Connection error: {str(e)}")
                if attempt < self._config.max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                raise last_error

        raise last_error or APIError("Max retries exceeded")

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class MockProvider(LLMProvider):
    """
    Mock provider for testing purposes.

    Returns predefined responses without making actual API calls.
    """

    def __init__(self, config: ProviderConfig):
        self._config = config
        self._responses: list[dict] = []
        self._stream_index = 0
        self._stream_responses: list[dict] = []

    @property
    def config(self) -> ProviderConfig:
        return self._config

    @property
    def model(self) -> str:
        return self._config.model

    def set_responses(self, responses: list[dict]) -> None:
        """Set predefined non-streaming responses."""
        self._responses = responses
        self._stream_index = 0

    def set_stream_responses(self, responses: list[dict]) -> None:
        """Set predefined streaming responses (list of events)."""
        self._stream_responses = responses
        self._stream_index = 0

    async def chat_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs: Any,
    ) -> dict:
        """Return a predefined non-streaming response."""
        if self._responses:
            return self._responses[0]
        return {
            "id": "mock-completion",
            "model": self._config.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "This is a mock response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "created": 1234567890,
        }

    async def chat_completion_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict, None]:
        """Yield predefined streaming responses."""
        if self._stream_responses:
            for response in self._stream_responses:
                yield response
            return

        # Default mock streaming response
        yield {"type": "content_block_delta", "index": 0, "delta": {"content": "This "}}
        yield {"type": "content_block_delta", "index": 0, "delta": {"content": "is "}}
        yield {"type": "content_block_delta", "index": 0, "delta": {"content": "a "}}
        yield {"type": "content_block_delta", "index": 0, "delta": {"content": "mock "}}
        yield {"type": "content_block_delta", "index": 0, "delta": {"content": "response."}}
        yield {"type": "usage", "prompt_tokens": 10, "completion_tokens": 5}
        yield {"type": "message_stop"}

    async def close(self) -> None:
        """No-op for mock provider."""
        pass


# Provider registry for looking up providers by name
_PROVIDERS: dict[str, type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "openai-compatible": OpenAIProvider,
    "mock": MockProvider,
}


def register_provider(name: str, provider_class: type[LLMProvider]) -> None:
    """Register a provider class by name."""
    _PROVIDERS[name.lower()] = provider_class


def create_provider(
    name: str | None,
    config: ProviderConfig,
) -> LLMProvider:
    """
    Create a provider instance by name.

    Args:
        name: Provider name (e.g., "openai", "anthropic"). If None, uses OpenAI-compatible.
        config: Provider configuration

    Returns:
        LLMProvider instance
    """
    if name is None:
        name = "openai-compatible"

    provider_class = _PROVIDERS.get(name.lower())
    if provider_class is None:
        raise ValueError(f"Unknown provider: {name}. Available: {list(_PROVIDERS.keys())}")

    return provider_class(config)
