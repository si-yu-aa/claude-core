"""BashTool - executes shell commands."""

from __future__ import annotations

import asyncio
import os
import shlex
from typing import Callable, TYPE_CHECKING

from claude_core.tools.base import Tool, ToolResult, build_tool
from claude_core.tools.permissions import build_permission_checker

if TYPE_CHECKING:
    from claude_core.models.tool import ToolUseContext

TIMEOUT_SECONDS = 60
READ_ONLY_COMMANDS = {"ls", "cat", "head", "tail", "grep", "find", "pwd", "echo"}
SHELL_WRITE_TOKENS = ("|", ">", ";", "&", "`", "$(", "<<")
FIND_WRITE_FLAGS = {"-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprintf", "-fls"}

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
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            abort_future = asyncio.get_event_loop().create_future()

            def on_abort() -> None:
                if not abort_future.done():
                    abort_future.set_result(context.abort_controller.signal.reason or "aborted")

            context.abort_controller.signal.add_event_listener("abort", on_abort)

            communicate_task = asyncio.create_task(process.communicate())

            try:
                done, pending = await asyncio.wait(
                    [communicate_task, abort_future],
                    timeout=timeout,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if abort_future in done:
                    communicate_task.cancel()
                    await _terminate_process(process)
                    return ToolResult(
                        tool_use_id=args.get("tool_use_id", ""),
                        content=f"Command aborted: {abort_future.result()}",
                        is_error=True,
                    )
                if communicate_task in done:
                    stdout, stderr = await communicate_task
                else:
                    communicate_task.cancel()
                    await _terminate_process(process)
                    return ToolResult(
                        tool_use_id=args.get("tool_use_id", ""),
                        content=f"Command timed out after {timeout} seconds",
                        is_error=True,
                    )
            except asyncio.CancelledError:
                await _terminate_process(process)
                raise

            output = stdout.decode() if stdout else ""
            error_output = stderr.decode() if stderr else ""

            if process.returncode != 0:
                return ToolResult(
                    tool_use_id=args.get("tool_use_id", ""),
                    content=f"Command failed with exit code {process.returncode}:\n{error_output or output}",
                    is_error=True,
                )

            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content=output or "(no output)",
                is_error=False,
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
        stripped = command.strip()
        if not stripped:
            return False

        if any(token in stripped for token in SHELL_WRITE_TOKENS):
            return False

        try:
            parts = shlex.split(stripped, posix=True)
        except ValueError:
            return False

        if not parts:
            return False

        executable = os.path.basename(parts[0])
        if executable not in READ_ONLY_COMMANDS:
            return False

        if any(part in FIND_WRITE_FLAGS or part.startswith("-exec") for part in parts[1:]):
            return False

        return True

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
        "check_permissions": build_permission_checker(
            lambda args: "bash:read" if is_read_only(args) else "bash:exec",
            "bash_command",
        ),
    })


async def _terminate_process(process: asyncio.subprocess.Process) -> None:
    """Best-effort process termination used by timeout and abort paths."""
    if process.returncode is not None:
        return

    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=2)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
