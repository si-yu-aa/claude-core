"""OpenAI-compatible LLM client."""

from __future__ import annotations

from typing import AsyncGenerator, Any, Optional
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
)
from claude_core.api.streaming import StreamEvent, parse_stream_response

DEFAULT_TIMEOUT = 120.0
MAX_RETRIES = 3

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

    async def chat_completion(
        self,
        messages: list[MessageParam | dict],
        tools: list[ToolParam] | None = None,
        **kwargs: Any,
    ) -> ChatCompletion:
        """Make a non-streaming chat completion request."""
        url = f"{self.base_url}/chat/completions"
        headers = self._build_headers()

        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            **kwargs,
        }

        if tools:
            body["tools"] = [self._tool_to_dict(t) for t in tools]

        response = await self._client.post(url, headers=headers, json=body)
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