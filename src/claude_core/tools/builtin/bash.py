"""BashTool - executes shell commands."""

from __future__ import annotations

import asyncio
from typing import Callable, TYPE_CHECKING

from claude_core.tools.base import Tool, ToolResult, build_tool

if TYPE_CHECKING:
    from claude_core.models.tool import ToolUseContext

TIMEOUT_SECONDS = 60

def create_bash_tool() -> Tool:
    async def call(
        args: dict,
        context: "ToolUseContext",
        can_use_tool: Callable,
        on_progress: Callable | None = None,
    ) -> ToolResult:
        command = args.get("command", "")
        timeout = args.get("timeout", TIMEOUT_SECONDS)

        if not command:
            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content="Error: command is required",
                is_error=True,
            )

        try:
            result = await asyncio.wait_for(
                asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=timeout,
            )

            stdout, stderr = await result.communicate()

            output = stdout.decode() if stdout else ""
            error_output = stderr.decode() if stderr else ""

            if result.returncode != 0:
                return ToolResult(
                    tool_use_id=args.get("tool_use_id", ""),
                    content=f"Command failed with exit code {result.returncode}:\n{error_output or output}",
                    is_error=True,
                )

            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content=output or "(no output)",
                is_error=False,
            )

        except asyncio.TimeoutError:
            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content=f"Command timed out after {timeout} seconds",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content=f"Error executing command: {str(e)}",
                is_error=True,
            )

    def is_concurrency_safe(args: dict) -> bool:
        return False

    def is_read_only(args: dict) -> bool:
        command = args.get("command", "")
        read_only_commands = ["ls", "cat", "head", "tail", "grep", "find", "pwd", "echo"]
        return any(command.strip().startswith(cmd) for cmd in read_only_commands)

    def interrupt_behavior() -> str:
        return "cancel"

    return build_tool({
        "name": "Bash",
        "description": "Execute a shell command.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds",
                    "default": 60
                },
            },
            "required": ["command"]
        },
        "call": call,
        "is_concurrency_safe": is_concurrency_safe,
        "is_read_only": is_read_only,
        "interrupt_behavior": interrupt_behavior,
    })
