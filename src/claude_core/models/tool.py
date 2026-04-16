"""Tool-related type definitions."""

from dataclasses import dataclass, field
from typing import Any, Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from claude_core.models.message import Message

@dataclass
class ToolUseBlock:
    """A tool use block from the LLM response."""
    id: str
    name: str
    input: dict[str, Any]
    type: str = "tool_use"

@dataclass
class ToolProgress:
    """Progress update during tool execution."""
    tool_use_id: str
    data: dict

@dataclass
class ToolUseContext:
    """Context passed to tool execution."""
    options: "ToolUseContextOptions"
    abort_controller: "AbortController"
    messages: list["Message"] = field(default_factory=list)
    agent_id: Optional[str] = None
    query_tracking: Optional["QueryChainTracking"] = None

@dataclass
class ToolUseContextOptions:
    """Options for tool use context."""
    commands: list[Any] = field(default_factory=list)
    debug: bool = False
    main_loop_model: str = "gpt-4o"
    tools: list["ToolDefinition"] = field(default_factory=list)
    verbose: bool = False
    thinking_config: Optional[dict] = None
    mcp_clients: list[Any] = field(default_factory=list)
    mcp_resources: dict[str, list[Any]] = field(default_factory=dict)
    is_non_interactive_session: bool = False
    agent_definitions: dict = field(default_factory=dict)
    max_budget_usd: Optional[float] = None
    custom_system_prompt: Optional[str] = None
    append_system_prompt: Optional[str] = None
    refresh_tools: Optional[Callable[[], list["ToolDefinition"]]] = None

@dataclass
class QueryChainTracking:
    """Tracking for nested query chains."""
    chain_id: str
    depth: int

@dataclass
class MessageUpdate:
    """Update from tool execution."""
    message: Optional[Any] = None
    new_context: Optional[ToolUseContext] = None
    context_modifier: Optional["ContextModifier"] = None

@dataclass
class ContextModifier:
    """Modifier for tool use context."""
    tool_use_id: str
    modify_context: Callable[[ToolUseContext], ToolUseContext]

@dataclass
class ToolDefinition:
    """Tool definition (interface only, actual tools are in tools/base.py)."""
    name: str
    description: str
    input_schema: dict
