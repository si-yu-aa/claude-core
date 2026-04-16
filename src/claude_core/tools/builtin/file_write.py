"""FileWriteTool - writes content to files."""

from __future__ import annotations

from typing import Callable, TYPE_CHECKING
import os

from claude_core.tools.base import Tool, ToolResult, build_tool

if TYPE_CHECKING:
    from claude_core.models.tool import ToolUseContext

def create_file_write_tool() -> Tool:
    async def call(
        args: dict,
        context: "ToolUseContext",
        can_use_tool: Callable,
        on_progress: Callable | None = None,
    ) -> ToolResult:
        file_path = args.get("file_path")
        content = args.get("content", "")

        if not file_path:
            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content="Error: file_path is required",
                is_error=True,
            )

        try:
            # Ensure directory exists
            dir_path = os.path.dirname(file_path)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)

            with open(file_path, "w") as f:
                f.write(content)

            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content=f"Successfully wrote to {file_path}",
                is_error=False,
            )
        except Exception as e:
            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content=f"Error writing file: {str(e)}",
                is_error=True,
            )

    def is_concurrency_safe(args: dict) -> bool:
        return False

    return build_tool({
        "name": "FileWrite",
        "description": "Write content to a file. Creates new file or overwrites existing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to write"},
                "content": {"type": "string", "description": "Content to write to the file"},
            },
            "required": ["file_path", "content"],
        },
        "call": call,
        "is_concurrency_safe": is_concurrency_safe,
    })