"""GrepTool - search file contents."""

from __future__ import annotations

from typing import Callable, TYPE_CHECKING
import os
import re
import fnmatch

from claude_core.tools.base import Tool, ToolResult, build_tool

if TYPE_CHECKING:
    from claude_core.models.tool import ToolUseContext

def create_grep_tool() -> Tool:
    async def call(
        args: dict,
        context: "ToolUseContext",
        can_use_tool: Callable,
        on_progress: Callable | None = None,
    ) -> ToolResult:
        pattern = args.get("pattern")
        base_dir = args.get("base_dir", os.getcwd())
        case_sensitive = args.get("case_sensitive", False)
        file_pattern = args.get("file_pattern", "*")

        if not pattern:
            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content="Error: pattern is required",
                is_error=True,
            )

        if not os.path.isdir(base_dir):
            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content=f"Error: Directory not found: {base_dir}",
                is_error=True,
            )

        def matches_pattern(filename: str, pattern: str) -> bool:
            """Check if filename matches the pattern."""
            if pattern == "*":
                return True
            if "*." in pattern:
                return fnmatch.fnmatch(filename, pattern)
            return pattern in filename

        try:
            # Compile regex
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags)

            matches = []
            max_results = 100

            # Walk directory
            for root, dirs, files in os.walk(base_dir):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]

                for filename in files:
                    if filename.startswith('.'):
                        continue
                    if not matches_pattern(filename, file_pattern):
                        continue

                    filepath = os.path.join(root, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                            for line_num, line in enumerate(f, 1):
                                if regex.search(line):
                                    rel_path = os.path.relpath(filepath, base_dir)
                                    matches.append(f"{rel_path}:{line_num}: {line.rstrip()}")
                                    if len(matches) >= max_results:
                                        break
                    except Exception:
                        continue

                if len(matches) >= max_results:
                    break

            if not matches:
                return ToolResult(
                    tool_use_id=args.get("tool_use_id", ""),
                    content=f"No matches found for pattern: {pattern}",
                    is_error=False,
                )

            result_lines = [f"Found {len(matches)} match(es):"]
            result_lines.extend(matches[:max_results])
            if len(matches) > max_results:
                result_lines.append(f"... and {len(matches) - max_results} more matches")

            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content="\n".join(result_lines),
                is_error=False,
            )
        except Exception as e:
            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content=f"Error searching: {str(e)}",
                is_error=True,
            )

    def is_concurrency_safe(args: dict) -> bool:
        return True

    return build_tool({
        "name": "Grep",
        "description": "Search file contents for a pattern.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Search pattern (regex)"},
                "base_dir": {"type": "string", "description": "Directory to search in"},
                "file_pattern": {"type": "string", "description": "File pattern to match (*.txt, *.py)"},
                "case_sensitive": {"type": "boolean", "description": "Case sensitive search"},
            },
            "required": ["pattern"],
        },
        "call": call,
        "is_concurrency_safe": is_concurrency_safe,
    })