"""Claude Core - Claude Code functionality in Python."""

__version__ = "0.1.0"

# Core engine
from claude_core.engine.query_engine import QueryEngine
from claude_core.engine.config import QueryEngineConfig
from claude_core.engine.types import QueryParams, StreamEvent

# Models
from claude_core.models.message import UserMessage, AssistantMessage, create_user_message

# Tools
from claude_core.tools.base import Tool, ToolResult, ToolImpl, build_tool

# API
from claude_core.api.client import LLMClient
from claude_core.api.errors import APIError, RateLimitError, AuthenticationError

__all__ = [
    # Version
    "__version__",
    # Engine
    "QueryEngine",
    "QueryEngineConfig",
    "QueryParams",
    "StreamEvent",
    # Models
    "UserMessage",
    "AssistantMessage",
    "create_user_message",
    # Tools
    "Tool",
    "ToolResult",
    "ToolImpl",
    "build_tool",
    # API
    "LLMClient",
    "APIError",
    "RateLimitError",
    "AuthenticationError",
]
