"""Provider abstractions and adapters for LLM request construction."""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Protocol

from claude_core.api.errors import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    InvalidRequestError,
    RateLimitError,
    is_retryable_error,
)


@dataclass
class ProviderConfig:
    """Configuration for a provider-backed client."""

    base_url: str
    api_key: str
    model: str
    timeout: float = 120.0
    max_retries: int = 3
    initial_retry_delay: float = 1.0


class LLMProvider(ABC):
    """Abstract provider interface used by the engine layer."""

    @property
    @abstractmethod
    def config(self) -> ProviderConfig:
        ...

    @property
    @abstractmethod
    def model(self) -> str:
        ...

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs: Any,
    ) -> dict:
        ...

    @abstractmethod
    async def chat_completion_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict, None]:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible provider implementation."""

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
        return {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }

    def _map_status_to_error(self, response: Any) -> APIError:
        status = response.status_code
        try:
            data = response.json()
            error_msg = data.get("error", {}).get("message", "") or data.get("message", "Unknown error")
        except Exception:
            error_msg = "Unknown error"

        if status == 401:
            return AuthenticationError(error_msg)
        if status == 403:
            return AuthenticationError("Access forbidden")
        if status == 400:
            return InvalidRequestError(error_msg, body=response.json() if response.content else None)
        if status == 429:
            retry_after = response.headers.get("retry-after")
            return RateLimitError(error_msg, retry_after=int(retry_after) if retry_after else None)
        if status >= 500:
            return APIConnectionError(f"Server error: {error_msg}")
        return APIError(f"HTTP {status}: {error_msg}", status_code=status)

    async def _get_client(self) -> Any:
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
                        retry_delay *= 2
                        continue
                    raise error

                return response.json()

            except APIError:
                raise
            except Exception as exc:
                last_error = APIConnectionError(f"Connection error: {str(exc)}")
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
                        raise error

                    prompt_tokens = 0
                    completion_tokens = 0
                    usage_recorded = False
                    buffered_tool_calls: dict[int, Any] = {}

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue

                        if not line.startswith("data: "):
                            continue

                        data = line[6:]
                        if data == "[DONE]":
                            for index in sorted(buffered_tool_calls):
                                buffered = buffered_tool_calls[index]
                                if not buffered.id:
                                    continue
                                try:
                                    tool_input = json.loads(buffered.arguments or "{}")
                                except json.JSONDecodeError:
                                    tool_input = {}
                                yield {
                                    "type": "tool_use",
                                    "tool_use_id": buffered.id,
                                    "name": buffered.name,
                                    "input": tool_input,
                                }
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

                        if "choices" not in chunk:
                            continue

                        for choice in chunk["choices"]:
                            delta = choice.get("delta", {})

                            if delta.get("content"):
                                yield {
                                    "type": "content_block_delta",
                                    "index": choice.get("index", 0),
                                    "delta": {"content": delta["content"]},
                                }

                            if delta.get("tool_calls"):
                                for tc in delta["tool_calls"]:
                                    index = tc.get("index", 0)
                                    if index not in buffered_tool_calls:
                                        buffered_tool_calls[index] = type(
                                            "BufferedToolCall",
                                            (),
                                            {"id": "", "name": "", "arguments": ""},
                                        )()

                                    buffered = buffered_tool_calls[index]
                                    if tc.get("id"):
                                        buffered.id = tc["id"]
                                    function = tc.get("function", {})
                                    if function.get("name"):
                                        buffered.name = function["name"]
                                    if function.get("arguments"):
                                        buffered.arguments += function["arguments"]

                            if choice.get("finish_reason"):
                                for index in sorted(buffered_tool_calls):
                                    buffered = buffered_tool_calls[index]
                                    if not buffered.id:
                                        continue
                                    try:
                                        tool_input = json.loads(buffered.arguments or "{}")
                                    except json.JSONDecodeError:
                                        tool_input = {}
                                    yield {
                                        "type": "tool_use",
                                        "tool_use_id": buffered.id,
                                        "name": buffered.name,
                                        "input": tool_input,
                                    }
                                buffered_tool_calls.clear()
                                yield {"type": "message_stop"}

                return

            except APIError:
                raise
            except Exception as exc:
                last_error = APIConnectionError(f"Connection error: {str(exc)}")
                if attempt < self._config.max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                raise last_error

        raise last_error or APIError("Max retries exceeded")

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


class MockProvider(LLMProvider):
    """Mock provider for tests."""

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
        self._responses = responses
        self._stream_index = 0

    def set_stream_responses(self, responses: list[dict]) -> None:
        self._stream_responses = responses
        self._stream_index = 0

    async def chat_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs: Any,
    ) -> dict:
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
        if self._stream_responses:
            for response in self._stream_responses:
                yield response
            return

        yield {"type": "content_block_delta", "index": 0, "delta": {"content": "This "}}
        yield {"type": "content_block_delta", "index": 0, "delta": {"content": "is "}}
        yield {"type": "content_block_delta", "index": 0, "delta": {"content": "a "}}
        yield {"type": "content_block_delta", "index": 0, "delta": {"content": "mock "}}
        yield {"type": "content_block_delta", "index": 0, "delta": {"content": "response."}}
        yield {"type": "usage", "prompt_tokens": 10, "completion_tokens": 5}
        yield {"type": "message_stop"}

    async def close(self) -> None:
        pass


class ProviderAdapter(Protocol):
    """Interface for provider-specific request construction."""

    name: str
    default_base_url: str

    def build_headers(self, api_key: str) -> dict[str, str]:
        ...

    def build_chat_completions_url(self, base_url: str) -> str:
        ...

    def build_request_body(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class OpenAIProviderAdapter:
    """Default OpenAI-compatible request adapter."""

    name: str = "openai"
    default_base_url: str = "https://api.openai.com/v1"

    def build_headers(self, api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def build_chat_completions_url(self, base_url: str) -> str:
        return f"{base_url.rstrip('/')}/chat/completions"

    def build_request_body(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
            **kwargs,
        }
        if tools:
            body["tools"] = tools
        return body


@dataclass(frozen=True)
class GeminiProviderAdapter(OpenAIProviderAdapter):
    """Gemini OpenAI-compatible endpoint adapter."""

    name: str = "gemini"
    default_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"


_PROVIDERS: dict[str, type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "openai-compatible": OpenAIProvider,
    "mock": MockProvider,
}

PROVIDERS: dict[str, ProviderAdapter] = {
    "openai": OpenAIProviderAdapter(),
    "gemini": GeminiProviderAdapter(),
}


def register_provider(name: str, provider_class: type[LLMProvider]) -> None:
    """Register a provider class by name."""

    _PROVIDERS[name.lower()] = provider_class


def create_provider(name: str | None, config: ProviderConfig) -> LLMProvider:
    """Create a provider instance by name."""

    if name is None:
        name = "openai-compatible"

    provider_class = _PROVIDERS.get(name.lower())
    if provider_class is None:
        raise ValueError(f"Unknown provider: {name}. Available: {list(_PROVIDERS.keys())}")

    return provider_class(config)


def get_provider_adapter(name: str) -> ProviderAdapter:
    """Resolve a provider adapter by name."""

    normalized = name.strip().lower()
    if normalized not in PROVIDERS:
        available = ", ".join(sorted(PROVIDERS))
        raise ValueError(f"Unknown provider '{name}'. Available providers: {available}")
    return PROVIDERS[normalized]
