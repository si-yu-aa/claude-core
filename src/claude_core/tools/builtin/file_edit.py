"""FileEditTool - edits file content using search and replace."""

from __future__ import annotations

from typing import Callable, TYPE_CHECKING
import os
import difflib

from claude_core.tools.base import Tool, ToolResult, build_tool

if TYPE_CHECKING:
    from claude_core.models.tool import ToolUseContext

def create_file_edit_tool() -> Tool:
    async def call(
        args: dict,
        context: "ToolUseContext",
        can_use_tool: Callable,
        on_progress: Callable | None = None,
    ) -> ToolResult:
        file_path = args.get("file_path")
        search = args.get("search")
        replace = args.get("replace", "")

        if not file_path:
            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content="Error: file_path is required",
                is_error=True,
            )

        if not search:
            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content="Error: search string is required",
                is_error=True,
            )

        if not os.path.exists(file_path):
            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content=f"Error: File not found: {file_path}",
                is_error=True,
            )

        try:
            with open(file_path, "r") as f:
                original_content = f.read()

            if search not in original_content:
                return ToolResult(
                    tool_use_id=args.get("tool_use_id", ""),
                    content=f"Error: Search string not found in file: {search}",
                    is_error=True,
                )

            new_content = original_content.replace(search, replace)

            # Show diff
            diff = list(difflib.unified_diff(
                original_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=file_path,
                tofile=file_path,
            ))
            diff_text = "".join(diff[:20])  # Limit diff output

            with open(file_path, "w") as f:
                f.write(new_content)

            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content=f"Successfully edited {file_path}\n\nDiff:\n{diff_text or '(no visible changes)'}",
                is_error=False,
            )
        except Exception as e:
            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content=f"Error editing file: {str(e)}",
                is_error=True,
            )

    def is_concurrency_safe(args: dict) -> bool:
        return False

    return build_tool({
        "name": "FileEdit",
        "description": "Edit a file by replacing text. Uses search and replace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to edit"},
                "search": {"type": "string", "description": "Text to search for"},
                "replace": {"type": "string", "description": "Text to replace with"},
            },
            "required": ["file_path", "search"],
        },
        "call": call,
        "is_concurrency_safe": is_concurrency_safe,
    })