"""Tool base types and utilities."""

from __future__ import annotations

from typing import Protocol, Callable, Any, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from claude_core.models.tool import ToolUseContext
    from claude_core.models.message import Message

InputSchema = Any

@dataclass
class ValidationResult:
    """Result of input validation."""
    result: bool
    message: str = ""
    error_code: int = 0

@dataclass
class PermissionResult:
    """Result of permission check."""
    behavior: str  # "allow", "deny", "ask"
    updated_input: dict[str, Any] | None = None
    decision_classification: str | None = None

@dataclass
class ToolResult:
    """Result of tool execution."""
    tool_use_id: str
    content: str | list[dict]
    is_error: bool = False
    new_messages: list["Message"] | None = None
    context_modifier: Callable[["ToolUseContext"], "ToolUseContext"] | None = None

class Tool(Protocol):
    """
    Tool interface definition.
    """

    name: str
    description: str
    input_schema: InputSchema

    async def call(
        self,
        args: dict[str, Any],
        context: "ToolUseContext",
        can_use_tool: Callable,
        on_progress: Callable | None = None,
    ) -> ToolResult:
        ...

    def is_enabled(self) -> bool:
        return True

    def is_concurrency_safe(self, args: dict[str, Any]) -> bool:
        return False

    def is_read_only(self, args: dict[str, Any]) -> bool:
        return False

    def is_destructive(self, args: dict[str, Any]) -> bool:
        return False

    def interrupt_behavior(self) -> str:
        return "block"

class ToolImpl:
    """
    Tool implementation class with attribute access.
    """
    def __init__(self, name: str, description: str, input_schema: Any):
        self.name = name
        self.description = description
        self.input_schema = input_schema

    def is_enabled(self) -> bool:
        return True

    def is_concurrency_safe(self, args: dict[str, Any]) -> bool:
        return False

    def is_read_only(self, args: dict[str, Any]) -> bool:
        return False

    def is_destructive(self, args: dict[str, Any]) -> bool:
        return False

    def interrupt_behavior(self) -> str:
        return "block"

def build_tool(tool_def: dict) -> Tool:
    """
    Build a complete Tool from a partial definition.
    """
    tool = ToolImpl(
        name=tool_def["name"],
        description=tool_def.get("description", ""),
        input_schema=tool_def["input_schema"],
    )

    # Override defaults with user-provided callables if present
    if "is_enabled" in tool_def:
        tool.is_enabled = tool_def["is_enabled"]
    if "is_concurrency_safe" in tool_def:
        tool.is_concurrency_safe = tool_def["is_concurrency_safe"]
    if "is_read_only" in tool_def:
        tool.is_read_only = tool_def["is_read_only"]
    if "is_destructive" in tool_def:
        tool.is_destructive = tool_def["is_destructive"]
    if "interrupt_behavior" in tool_def:
        tool.interrupt_behavior = tool_def["interrupt_behavior"]

    # Add any additional user implementations (like 'call')
    for key, value in tool_def.items():
        if key not in ("name", "description", "input_schema", "is_enabled", "is_concurrency_safe", "is_read_only", "is_destructive", "interrupt_behavior"):
            setattr(tool, key, value)

    return tool