"""API module for LLM communication."""

from claude_core.api.client import LLMClient
from claude_core.api.types import (
    MessageParam,
    ToolParam,
    FunctionDefinition,
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

__all__ = [
    "LLMClient",
    "MessageParam",
    "ToolParam",
    "FunctionDefinition",
    "ChatCompletion",
    "ChatCompletionChoice",
    "Usage",
    "APIError",
    "RateLimitError",
    "AuthenticationError",
    "InvalidRequestError",
    "APIConnectionError",
    "is_retryable_error",
]