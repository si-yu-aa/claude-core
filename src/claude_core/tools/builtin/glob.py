"""GlobTool - file pattern matching."""

from __future__ import annotations

from typing import Callable, TYPE_CHECKING
import os
import glob as glob_module

from claude_core.tools.base import Tool, ToolResult, build_tool

if TYPE_CHECKING:
    from claude_core.models.tool import ToolUseContext

def create_glob_tool() -> Tool:
    async def call(
        args: dict,
        context: "ToolUseContext",
        can_use_tool: Callable,
        on_progress: Callable | None = None,
    ) -> ToolResult:
        pattern = args.get("pattern", "*")
        base_dir = args.get("base_dir", os.getcwd())
        recursive = args.get("recursive", False)

        if not os.path.isdir(base_dir):
            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content=f"Error: Directory not found: {base_dir}",
                is_error=True,
            )

        try:
            # Build full pattern
            if recursive or "**" in pattern:
                full_pattern = os.path.join(base_dir, "**", pattern)
                matches = glob_module.glob(full_pattern, recursive=True)
            else:
                full_pattern = os.path.join(base_dir, pattern)
                matches = glob_module.glob(full_pattern)

            # Filter to only files
            matches = [m for m in matches if os.path.isfile(m)]

            if not matches:
                return ToolResult(
                    tool_use_id=args.get("tool_use_id", ""),
                    content="No files found matching pattern",
                    is_error=False,
                )

            # Format results
            result_lines = [f"Found {len(matches)} file(s):"]
            for match in matches[:100]:  # Limit output
                rel_path = os.path.relpath(match, base_dir)
                result_lines.append(f"  - {rel_path}")
            if len(matches) > 100:
                result_lines.append(f"  ... and {len(matches) - 100} more")

            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content="\n".join(result_lines),
                is_error=False,
            )
        except Exception as e:
            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content=f"Error searching files: {str(e)}",
                is_error=True,
            )

    def is_concurrency_safe(args: dict) -> bool:
        return True

    return build_tool({
        "name": "Glob",
        "description": "Find files matching a glob pattern.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g., *.txt, **/*.py)"},
                "base_dir": {"type": "string", "description": "Base directory to search from"},
                "recursive": {"type": "boolean", "description": "Search recursively"},
            },
            "required": ["pattern"],
        },
        "call": call,
        "is_concurrency_safe": is_concurrency_safe,
    })