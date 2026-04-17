"""OpenAI-compatible LLM client."""

from __future__ import annotations

import asyncio
from typing import Any
import httpx

from claude_core.api.types import (
    MessageParam,
    ToolParam,
    ChatCompletion,
    ChatCompletionChoice,
    Usage,
)
from claude_core.api.errors import (
    APIError,
    RateLimitError,
    AuthenticationError,
    InvalidRequestError,
    APIConnectionError,
    is_retryable_error,
)

DEFAULT_TIMEOUT = 120.0
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0

class LLMClient:
    """
    OpenAI-compatible LLM client.

    Supports any API that implements the OpenAI Chat Completions protocol,
    including Ollama, vLLM, DeepSeek, etc.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "gpt-4o",
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    def _build_headers(self) -> dict[str, str]:
        """Build request headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _map_status_to_error(self, response: httpx.Response) -> APIError:
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

    async def chat_completion(
        self,
        messages: list[MessageParam | dict],
        tools: list[ToolParam] | None = None,
        **kwargs: Any,
    ) -> ChatCompletion:
        """Make a non-streaming chat completion request with retry logic."""
        url = f"{self.base_url}/chat/completions"
        headers = self._build_headers()

        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            **kwargs,
        }

        if tools:
            body["tools"] = [self._tool_to_dict(t) for t in tools]

        last_error: APIError | None = None
        retry_delay = INITIAL_RETRY_DELAY

        for attempt in range(self.max_retries):
            try:
                response = await self._client.post(url, headers=headers, json=body)

                if response.status_code != 200:
                    error = self._map_status_to_error(response)
                    last_error = error

                    if not is_retryable_error(error):
                        raise error

                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        raise error

                data = response.json()
                return ChatCompletion(
                    id=data.get("id", ""),
                    model=data.get("model", self.model),
                    choices=[
                        ChatCompletionChoice(
                            index=c.get("index", 0),
                            message=c.get("message", {}),
                            finish_reason=c.get("finish_reason", ""),
                        )
                        for c in data.get("choices", [])
                    ],
                    usage=Usage(
                        prompt_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                        completion_tokens=data.get("usage", {}).get("completion_tokens", 0),
                        total_tokens=data.get("usage", {}).get("total_tokens", 0),
                    ),
                    created=data.get("created", 0),
                )

            except APIError:
                raise
            except httpx.HTTPError as e:
                last_error = APIConnectionError(f"Connection error: {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                raise last_error

        raise last_error or APIError("Max retries exceeded")

    def _tool_to_dict(self, tool: ToolParam) -> dict:
        """Convert a ToolParam to a dict."""
        return {
            "type": "function",
            "function": {
                "name": tool.function.name,
                "description": tool.function.description,
                "parameters": tool.function.parameters,
            }
        }