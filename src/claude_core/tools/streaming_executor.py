"""Streaming Tool Executor - executes tools as they arrive from LLM stream."""

from __future__ import annotations

from typing import AsyncGenerator, Callable, Awaitable, Any, TYPE_CHECKING
from dataclasses import dataclass, field, replace
from enum import Enum
import asyncio

if TYPE_CHECKING:
    from claude_core.tools.base import Tool, ToolResult
    from claude_core.models.tool import ToolUseContext, ToolUseBlock
    from claude_core.models.message import Message

from claude_core.models.tool import MessageUpdate
from claude_core.tools.base import tool_matches_name
from claude_core.utils.abort import create_child_abort_controller

class ToolStatus(Enum):
    QUEUED = "queued"
    EXECUTING = "executing"
    COMPLETED = "completed"
    YIELDED = "yielded"

@dataclass
class TrackedTool:
    id: str
    block: "ToolUseBlock"
    assistant_message: Any
    status: ToolStatus = ToolStatus.QUEUED
    is_concurrency_safe: bool = False
    promise: asyncio.Task[Any] | None = field(default=None)
    results: list["Message"] = field(default_factory=list)
    pending_progress: list["Message"] = field(default_factory=list)
    context_modifiers: list[Callable] = field(default_factory=list)
    context_modifiers_applied: bool = False

def find_tool_by_name(tools: list["Tool"], name: str) -> "Tool | None":
    for tool in tools:
        if tool_matches_name(tool, name):
            return tool
    return None

def create_user_message(
    content: list[dict],
    tool_use_id: str,
    is_error: bool = False,
    tool_use_result: str | None = None,
    source_tool_assistant_uuid: str | None = None,
) -> "Message":
    from claude_core.utils.uuid import generate_uuid
    from claude_core.models.message import UserMessage

    return UserMessage(
        uuid=generate_uuid(),
        message={
            "role": "user",
            "content": content,
            "sourceToolAssistantUUID": source_tool_assistant_uuid,
        },
        tool_use_result=tool_use_result,
    )

class StreamingToolExecutor:
    """
    Executes tools as they stream in with concurrency control.
    """

    def __init__(
        self,
        tool_definitions: list["Tool"],
        can_use_tool: Callable,
        tool_use_context: "ToolUseContext",
    ):
        self._tools: list[TrackedTool] = []
        self._tool_definitions = tool_definitions
        self._can_use_tool = can_use_tool
        self._context = tool_use_context
        self._has_errored = False
        self._errored_tool_description = ""
        self._sibling_abort_controller = create_child_abort_controller(
            tool_use_context.abort_controller
        )
        self._discarded = False
        self._progress_available_resolve: Callable | None = None

    def discard(self) -> None:
        self._discarded = True
        self._sibling_abort_controller.abort("streaming_fallback")

    def add_tool(self, block: "ToolUseBlock", assistant_message: Any) -> None:
        tool_def = find_tool_by_name(self._tool_definitions, block.name)

        if not tool_def:
            self._tools.append(TrackedTool(
                id=block.id,
                block=block,
                assistant_message=assistant_message,
                status=ToolStatus.COMPLETED,
                is_concurrency_safe=True,
                results=[create_user_message(
                    content=[{
                        "type": "tool_result",
                        "content": f"<tool_use_error>Error: No such tool available: {block.name}</tool_use_error>",
                        "is_error": True,
                        "tool_use_id": block.id,
                    }],
                    tool_use_id=block.id,
                    is_error=True,
                    tool_use_result=f"Error: No such tool available: {block.name}",
                    source_tool_assistant_uuid=assistant_message.uuid if hasattr(assistant_message, "uuid") else None,
                )],
            ))
            return

        parsed_input = block.input
        is_concurrency_safe = False
        if parsed_input:
            try:
                is_concurrency_safe = tool_def.is_concurrency_safe(parsed_input)
            except Exception:
                is_concurrency_safe = False

        self._tools.append(TrackedTool(
            id=block.id,
            block=block,
            assistant_message=assistant_message,
            status=ToolStatus.QUEUED,
            is_concurrency_safe=is_concurrency_safe,
        ))

        asyncio.create_task(self._process_queue())

    def _can_execute_tool(self, is_concurrency_safe: bool) -> bool:
        executing = [t for t in self._tools if t.status == ToolStatus.EXECUTING]
        if not executing:
            return True
        return is_concurrency_safe and all(t.is_concurrency_safe for t in executing)

    async def _process_queue(self) -> None:
        for tool in self._tools:
            if tool.status != ToolStatus.QUEUED:
                continue

            if self._can_execute_tool(tool.is_concurrency_safe):
                tool.status = ToolStatus.EXECUTING
                tool.promise = asyncio.create_task(self._execute_tool(tool))
                if not tool.is_concurrency_safe:
                    break
            elif not tool.is_concurrency_safe:
                break

    async def _execute_tool(self, tool: TrackedTool) -> None:
        messages: list[Message] = []
        context_modifiers: list[Callable] = []

        abort_reason = self._get_abort_reason(tool)
        if abort_reason:
            messages.append(self._create_synthetic_error(tool, abort_reason))
            tool.results = messages
            tool.status = ToolStatus.COMPLETED
            return

        tool_abort_controller = create_child_abort_controller(self._sibling_abort_controller)
        tool_context = replace(self._context, abort_controller=tool_abort_controller)

        try:
            tool_def = find_tool_by_name(self._tool_definitions, tool.block.name)
            if not tool_def:
                messages.append(self._create_synthetic_error(tool, "unknown_tool"))
                tool.results = messages
                tool.status = ToolStatus.COMPLETED
                return

            # Validate input before execution
            validation_result = await tool_def.validate_input(
                tool.block.input or {},
                tool_context,
            )
            if not validation_result.result:
                error_msg = validation_result.message or "Input validation failed"
                messages.append(create_user_message(
                    content=[{
                        "type": "tool_result",
                        "content": f"<tool_use_error>Validation error: {error_msg}</tool_use_error>",
                        "is_error": True,
                        "tool_use_id": tool.id,
                    }],
                    tool_use_id=tool.id,
                    is_error=True,
                    tool_use_result=f"Validation failed: {error_msg}",
                ))
                tool.results = messages
                tool.status = ToolStatus.COMPLETED
                return

            # Check permissions before execution
            permission_result = await tool_def.check_permissions(
                tool.block.input or {},
                tool_context,
            )
            if permission_result.behavior in {"deny", "ask"}:
                error_msg = permission_result.message or (
                    "Permission denied"
                    if permission_result.behavior == "deny"
                    else "Permission requires user confirmation"
                )
                messages.append(create_user_message(
                    content=[{
                        "type": "tool_result",
                        "content": f"<tool_use_error>{error_msg}</tool_use_error>",
                        "is_error": True,
                        "tool_use_id": tool.id,
                    }],
                    tool_use_id=tool.id,
                    is_error=True,
                    tool_use_result=error_msg,
                ))
                tool.results = messages
                tool.status = ToolStatus.COMPLETED
                return

            call_args = permission_result.updated_input or tool.block.input or {}
            result = await tool_def.call(
                call_args,
                tool_context,
                self._can_use_tool,
                None,
            )

            content = result.content if isinstance(result.content, list) else [{"type": "text", "text": str(result.content)}]
            messages.append(create_user_message(
                content=[{
                    "type": "tool_result",
                    "content": content if isinstance(content, list) else str(content),
                    "is_error": result.is_error,
                    "tool_use_id": tool.id,
                }],
                tool_use_id=tool.id,
                is_error=result.is_error,
                tool_use_result=str(result.content),
                source_tool_assistant_uuid=tool.assistant_message.uuid if hasattr(tool.assistant_message, "uuid") else None,
            ))

            if result.context_modifier:
                context_modifiers.append(result.context_modifier)

        except Exception as e:
            self._has_errored = True
            self._errored_tool_description = f"{tool.block.name}"
            self._sibling_abort_controller.abort("sibling_error")
            messages.append(create_user_message(
                content=[{
                    "type": "tool_result",
                    "content": f"<tool_use_error>Error: {str(e)}</tool_use_error>",
                    "is_error": True,
                    "tool_use_id": tool.id,
                }],
                tool_use_id=tool.id,
                is_error=True,
                tool_use_result=str(e),
            ))
        finally:
            tool_abort_controller.dispose()

        tool.results = messages
        tool.context_modifiers = context_modifiers
        tool.status = ToolStatus.COMPLETED

        if not tool.is_concurrency_safe:
            for modifier in context_modifiers:
                self._context = modifier(self._context)
            tool.context_modifiers_applied = True

        asyncio.create_task(self._process_queue())

    def _get_abort_reason(self, tool: TrackedTool) -> str | None:
        if self._discarded:
            return "streaming_fallback"
        if self._has_errored:
            return "sibling_error"
        if self._sibling_abort_controller.signal.aborted:
            reason = self._sibling_abort_controller.signal.reason
            if reason == "streaming_fallback":
                return "streaming_fallback"
            if reason == "sibling_error":
                return "sibling_error"
            return "user_interrupted"
        return None

    def _create_synthetic_error(self, tool: TrackedTool, reason: str) -> "Message":
        content_map = {
            "user_interrupted": "Tool execution was cancelled by user",
            "sibling_error": f"Cancelled: parallel tool call {self._errored_tool_description} errored",
            "streaming_fallback": "Streaming fallback - tool execution discarded",
        }
        content = content_map.get(reason, f"Tool execution cancelled: {reason}")

        return create_user_message(
            content=[{
                "type": "tool_result",
                "content": f"<tool_use_error>{content}</tool_use_error>",
                "is_error": True,
                "tool_use_id": tool.id,
            }],
            tool_use_id=tool.id,
            is_error=True,
            tool_use_result=content,
        )

    def get_completed_results(self) -> "Generator[MessageUpdate, None]":
        if self._discarded:
            return

        for tool in self._tools:
            while tool.pending_progress:
                yield MessageUpdate(
                    message=tool.pending_progress.pop(0),
                    new_context=self._context,
                )

            if tool.status == ToolStatus.YIELDED:
                continue

            if tool.status == ToolStatus.COMPLETED and tool.results:
                tool.status = ToolStatus.YIELDED
                for msg in tool.results:
                    yield MessageUpdate(message=msg, new_context=self._context)

    async def get_remaining_results(self) -> AsyncGenerator["MessageUpdate", None]:
        if self._discarded:
            return

        while self._has_unfinished_tools():
            await self._process_queue()

            for result in self.get_completed_results():
                yield result

            if self._has_executing_tools() and not self._has_completed_results():
                if not self._has_pending_progress():
                    executing_promises = [
                        t.promise for t in self._tools
                        if t.status == ToolStatus.EXECUTING and t.promise
                    ]
                    progress_promise = asyncio.get_event_loop().create_future()
                    self._progress_available_resolve = progress_promise.set_result

                    if executing_promises:
                        done, pending = await asyncio.wait(
                            [*executing_promises, progress_promise],
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        if progress_promise in pending:
                            progress_promise.cancel()
                    else:
                        # Yield control when there are executing tools but no
                        # tracked promise object (defensive fallback).
                        await asyncio.sleep(0.01)

        for result in self.get_completed_results():
            yield result

    def get_updated_context(self) -> "ToolUseContext":
        """Return the updated context after tool execution.

        This should be called after get_remaining_results() to get
        the context modified by any context_modifiers from tools.
        """
        # Apply all pending context modifiers from completed tools
        for tool in self._tools:
            if (
                tool.status == ToolStatus.COMPLETED
                and tool.context_modifiers
                and not tool.context_modifiers_applied
            ):
                for modifier in tool.context_modifiers:
                    self._context = modifier(self._context)
                tool.context_modifiers_applied = True
        return self._context

    def _has_unfinished_tools(self) -> bool:
        return any(t.status != ToolStatus.YIELDED for t in self._tools)

    def _has_executing_tools(self) -> bool:
        return any(t.status == ToolStatus.EXECUTING for t in self._tools)

    def _has_completed_results(self) -> bool:
        return any(t.status == ToolStatus.COMPLETED for t in self._tools)

    def _has_pending_progress(self) -> bool:
        return any(t.pending_progress for t in self._tools)
