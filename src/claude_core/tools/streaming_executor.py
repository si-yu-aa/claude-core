"""Streaming Tool Executor - executes tools as they arrive from LLM stream."""

from __future__ import annotations

from typing import AsyncGenerator, Callable, Awaitable, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
import asyncio

if TYPE_CHECKING:
    from claude_core.tools.base import Tool, ToolResult
    from claude_core.models.tool import ToolUseContext, ToolUseBlock, MessageUpdate
    from claude_core.models.message import Message

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
    promise: Awaitable | None = field(default=None)
    results: list["Message"] = field(default_factory=list)
    pending_progress: list["Message"] = field(default_factory=list)
    context_modifiers: list[Callable] = field(default_factory=list)

def find_tool_by_name(tools: list["Tool"], name: str) -> "Tool | None":
    for tool in tools:
        if tool.name == name:
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
                await self._execute_tool(tool)
            elif not tool.is_concurrency_safe:
                break

    async def _execute_tool(self, tool: TrackedTool) -> None:
        tool.status = ToolStatus.EXECUTING

        messages: list[Message] = []
        context_modifiers: list[Callable] = []

        abort_reason = self._get_abort_reason(tool)
        if abort_reason:
            messages.append(self._create_synthetic_error(tool, abort_reason))
            tool.results = messages
            tool.status = ToolStatus.COMPLETED
            return

        tool_abort_controller = create_child_abort_controller(self._sibling_abort_controller)

        try:
            tool_def = find_tool_by_name(self._tool_definitions, tool.block.name)
            if not tool_def:
                messages.append(self._create_synthetic_error(tool, "unknown_tool"))
                tool.results = messages
                tool.status = ToolStatus.COMPLETED
                return

            result = await tool_def.call(
                tool.block.input or {},
                self._context,
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

        tool.results = messages
        tool.context_modifiers = context_modifiers
        tool.status = ToolStatus.COMPLETED

        if not tool.is_concurrency_safe:
            for modifier in context_modifiers:
                self._context = modifier(self._context)

        asyncio.create_task(self._process_queue())

    def _get_abort_reason(self, tool: TrackedTool) -> str | None:
        if self._discarded:
            return "streaming_fallback"
        if self._has_errored:
            return "sibling_error"
        if self._context.abort_controller.signal.aborted:
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
                        await asyncio.race([*executing_promises, progress_promise])

        for result in self.get_completed_results():
            yield result

    def _has_unfinished_tools(self) -> bool:
        return any(t.status != ToolStatus.YIELDED for t in self._tools)

    def _has_executing_tools(self) -> bool:
        return any(t.status == ToolStatus.EXECUTING for t in self._tools)

    def _has_completed_results(self) -> bool:
        return any(t.status == ToolStatus.COMPLETED for t in self._tools)

    def _has_pending_progress(self) -> bool:
        return any(t.pending_progress for t in self._tools)


def create_child_abort_controller(parent: "AbortController") -> "AbortController":
    from claude_core.utils.abort import AbortController

    child = AbortController()

    def propagate_to_parent():
        if not parent.signal.aborted:
            parent.abort(child.signal.reason or "child_abort")

    child.signal.add_event_listener("abort", propagate_to_parent)
    return child