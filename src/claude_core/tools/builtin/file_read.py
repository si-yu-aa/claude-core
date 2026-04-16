"""FileReadTool - reads files from the filesystem."""

from __future__ import annotations

from typing import Callable, TYPE_CHECKING
import os

from claude_core.tools.base import Tool, ToolResult, build_tool

if TYPE_CHECKING:
    from claude_core.models.tool import ToolUseContext

MAX_FILE_SIZE = 100_000

def create_file_read_tool() -> Tool:
    async def call(
        args: dict,
        context: "ToolUseContext",
        can_use_tool: Callable,
        on_progress: Callable | None = None,
    ) -> ToolResult:
        file_path = args.get("file_path")

        if not file_path:
            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content="Error: file_path is required",
                is_error=True,
            )

        if not os.path.exists(file_path):
            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content=f"Error: No such file: {file_path}",
                is_error=True,
            )

        file_size = os.path.getsize(file_path)

        if file_size > MAX_FILE_SIZE:
            with open(file_path, "r") as f:
                content = f.read(MAX_FILE_SIZE)
            content += f"\n... (truncated, {file_size} bytes total)"
        else:
            with open(file_path, "r") as f:
                content = f.read()

        return ToolResult(
            tool_use_id=args.get("tool_use_id", ""),
            content=content,
            is_error=False,
        )

    def is_read_only(args: dict) -> bool:
        return True

    def is_concurrency_safe(args: dict) -> bool:
        return True

    return build_tool({
        "name": "FileRead",
        "description": "Read the contents of a file from the filesystem.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The path to the file to read"
                },
            },
            "required": ["file_path"]
        },
        "call": call,
        "is_read_only": is_read_only,
        "is_concurrency_safe": is_concurrency_safe,
    })
