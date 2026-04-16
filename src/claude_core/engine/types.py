"""Query Engine type definitions."""

from dataclasses import dataclass, field
from typing import Any, Optional, Callable, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from claude_core.models.tool import ToolUseContext

class Continue:
    """Continue the query loop."""
    reason: str = "continue"

class Stop:
    """Stop the query loop."""
    def __init__(self, reason: str = "stop"):
        self.reason = reason

@dataclass
class QueryParams:
    """Parameters for the query function."""
    messages: list[Any]
    system_prompt: str
    user_context: dict[str, str]
    system_context: dict[str, str]
    can_use_tool: Callable
    tool_use_context: "ToolUseContext | None"
    fallback_model: Optional[str] = None
    query_source: str = "sdk"
    max_output_tokens_override: Optional[int] = None
    max_turns: Optional[int] = None
    skip_cache_write: bool = False
    task_budget: Optional[dict] = None

@dataclass
class QueryState:
    """State maintained across query loop iterations."""
    messages: list[Any]
    tool_use_context: "ToolUseContext | None"
    max_output_tokens_recovery_count: int = 0
    has_attempted_reactive_compact: bool = False
    max_output_tokens_override: Optional[int] = None
    pending_tool_use_summary: Optional[Any] = None
    stop_hook_active: Optional[bool] = None
    turn_count: int = 1
    transition: Optional[Continue | Stop] = None

@dataclass
class StreamEvent:
    """Base class for stream events."""
    type: str

@dataclass
class ContentBlockDeltaEvent(StreamEvent):
    """A content block delta event."""
    type: str = "content_block_delta"
    index: int = 0
    delta: dict = field(default_factory=dict)

@dataclass
class MessageDeltaEvent(StreamEvent):
    """A message delta event."""
    type: str = "message_delta"
    delta: dict = field(default_factory=dict)
    usage: Optional[dict] = None

@dataclass
class MessageStopEvent(StreamEvent):
    """A message stop event."""
    type: str = "message_stop"

@dataclass
class ToolUseEvent(StreamEvent):
    """A tool use event."""
    type: str = "tool_use"
    tool_use_id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)