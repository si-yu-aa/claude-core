"""Tool base types and utilities."""

from __future__ import annotations

from typing import Protocol, Callable, Any, TYPE_CHECKING, Awaitable
from dataclasses import dataclass
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from claude_core.models.tool import ToolUseContext, ToolPermissionContext
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
    behavior: str  # "allow", "deny", "ask", "passthrough"
    updated_input: dict[str, Any] | None = None
    message: str | None = None
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

    async def validate_input(
        self,
        input_data: dict[str, Any],
        context: "ToolUseContext",
    ) -> ValidationResult:
        """Validate tool input data."""
        return ValidationResult(result=True)

    async def check_permissions(
        self,
        input_data: dict[str, Any],
        context: "ToolUseContext",
    ) -> PermissionResult:
        """Check if tool has permission to execute with given input."""
        return PermissionResult(behavior="allow")

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
    def __init__(self, name: str, description: str, input_schema: Any, **kwargs: Any):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self._aliases = kwargs.get("aliases", [])
        self._search_hint = kwargs.get("search_hint")
        self._max_result_size_chars = kwargs.get("max_result_size_chars")
        for attr in (
            "is_enabled",
            "is_concurrency_safe",
            "is_read_only",
            "is_destructive",
            "interrupt_behavior",
            "validate_input",
            "check_permissions",
        ):
            if attr in kwargs:
                setattr(self, attr, kwargs[attr])

    async def validate_input(
        self,
        input_data: dict[str, Any],
        context: "ToolUseContext",
    ) -> ValidationResult:
        """Validate tool input data."""
        return ValidationResult(result=True)

    async def check_permissions(
        self,
        input_data: dict[str, Any],
        context: "ToolUseContext",
    ) -> PermissionResult:
        """Check if tool has permission to execute with given input."""
        return PermissionResult(behavior="allow")

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

    def aliases(self) -> list[str]:
        return list(self._aliases)

    def searchHint(self) -> str | None:
        return self._search_hint

    def maxResultSizeChars(self) -> int | None:
        return self._max_result_size_chars

    def getPath(self, args: dict[str, Any]) -> str | None:
        return args.get("path") or args.get("file_path")

    def isSearchOrReadCommand(self, args: dict[str, Any]) -> dict[str, str] | None:
        path = self.getPath(args)
        if path is None:
            return None
        lowered = self.name.lower()
        if "read" in lowered:
            return {"type": "read", "path": path}
        if "grep" in lowered or "glob" in lowered or "search" in lowered:
            return {"type": "search", "path": path}
        return None

def build_tool(tool_def: dict) -> Tool:
    """
    Build a complete Tool from a partial definition.
    """
    tool = ToolImpl(
        name=tool_def["name"],
        description=tool_def.get("description", ""),
        input_schema=tool_def["input_schema"],
        aliases=tool_def.get("aliases", []),
        search_hint=tool_def.get("search_hint"),
        max_result_size_chars=tool_def.get("max_result_size_chars"),
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
    if "validate_input" in tool_def:
        tool.validate_input = tool_def["validate_input"]
    if "check_permissions" in tool_def:
        tool.check_permissions = tool_def["check_permissions"]

    # Add any additional user implementations (like 'call')
    excluded_keys = (
        "name", "description", "input_schema", "is_enabled", "is_concurrency_safe",
        "is_read_only", "is_destructive", "interrupt_behavior", "validate_input",
        "check_permissions"
    )
    for key, value in tool_def.items():
        if key not in excluded_keys:
            setattr(tool, key, value)

    return tool


def tool_matches_name(tool: Tool, name: str) -> bool:
    """Return True when the tool name or alias matches."""
    if tool.name == name:
        return True
    aliases = []
    if hasattr(tool, "aliases"):
        aliases_attr = tool.aliases
        aliases = aliases_attr() if callable(aliases_attr) else aliases_attr
    return name in aliases
