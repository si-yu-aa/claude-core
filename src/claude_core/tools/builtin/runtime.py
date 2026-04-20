"""Runtime control tools for agents and background tasks."""

from __future__ import annotations

from typing import Callable, TYPE_CHECKING
import time

from claude_core.agents.runtime import AgentRuntime
from claude_core.agents.types import AgentStatus
from claude_core.tasks.types import BackgroundTaskTracker
from claude_core.tools.base import Tool, ToolResult, build_tool

if TYPE_CHECKING:
    from claude_core.models.tool import ToolUseContext


def create_send_message_tool() -> Tool:
    async def call(
        args: dict,
        context: "ToolUseContext",
        can_use_tool: Callable,
        on_progress: Callable | None = None,
    ) -> ToolResult:
        tool_use_id = args.get("tool_use_id", "")
        recipient_id = args.get("recipient_id", "")
        message = args.get("message", "")

        if not recipient_id:
            return ToolResult(tool_use_id=tool_use_id, content="Error: recipient_id is required", is_error=True)
        if not message:
            return ToolResult(tool_use_id=tool_use_id, content="Error: message is required", is_error=True)

        runtime = AgentRuntime.get_instance()
        agent = runtime.get_agent(recipient_id)
        if agent is None:
            return ToolResult(
                tool_use_id=tool_use_id,
                content=f"Error: Agent not found: {recipient_id}",
                is_error=True,
            )

        status = getattr(agent, "status", None)
        status_value = getattr(status, "value", None)
        if status_value is not None and status_value not in {"running", "paused", "idle"}:
            return ToolResult(
                tool_use_id=tool_use_id,
                content=f"Error: Agent is not accepting messages: {recipient_id} [{status_value or 'unknown'}]",
                is_error=True,
            )

        runtime.mailbox.send(getattr(context, "agent_id", None) or "system", recipient_id, message)
        if status_value == "paused" and hasattr(agent, "resume_background"):
            try:
                await agent.resume_background()
            except RuntimeError as exc:
                return ToolResult(
                    tool_use_id=tool_use_id,
                    content=str(exc),
                    is_error=True,
                )
        return ToolResult(
            tool_use_id=tool_use_id,
            content=f"Message sent to {recipient_id}",
            is_error=False,
        )

    return build_tool({
        "name": "SendMessage",
        "description": "Send a message to another running agent by agent ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipient_id": {"type": "string", "description": "Target agent ID"},
                "message": {"type": "string", "description": "Message content"},
            },
            "required": ["recipient_id", "message"],
        },
        "call": call,
        "is_concurrency_safe": lambda args: True,
        "is_read_only": lambda args: False,
    })


def create_agent_list_tool() -> Tool:
    async def call(
        args: dict,
        context: "ToolUseContext",
        can_use_tool: Callable,
        on_progress: Callable | None = None,
    ) -> ToolResult:
        tool_use_id = args.get("tool_use_id", "")
        runtime = AgentRuntime.get_instance()
        agents = runtime.list_agents()

        if not agents:
            return ToolResult(tool_use_id=tool_use_id, content="No registered agents", is_error=False)

        lines = [f"Agents ({len(agents)}):"]
        for agent in agents:
            lines.append(
                f"- {agent['agent_id']} [{agent['status']}] messages={agent['message_count']} inbox={agent['pending_inbox']}"
            )
        return ToolResult(tool_use_id=tool_use_id, content="\n".join(lines), is_error=False)

    return build_tool({
        "name": "AgentList",
        "description": "List registered runtime agents and their status.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
        "call": call,
        "is_concurrency_safe": lambda args: True,
        "is_read_only": lambda args: True,
    })


def create_agent_get_tool() -> Tool:
    async def call(
        args: dict,
        context: "ToolUseContext",
        can_use_tool: Callable,
        on_progress: Callable | None = None,
    ) -> ToolResult:
        tool_use_id = args.get("tool_use_id", "")
        agent_id = args.get("agent_id", "")
        if not agent_id:
            return ToolResult(tool_use_id=tool_use_id, content="Error: agent_id is required", is_error=True)

        runtime = AgentRuntime.get_instance()
        agent = runtime.describe_agent(agent_id)
        if agent is None:
            return ToolResult(tool_use_id=tool_use_id, content=f"Error: Agent not found: {agent_id}", is_error=True)

        lines = [
            f"Agent ID: {agent['agent_id']}",
            f"Status: {agent['status']}",
            f"Messages: {agent['message_count']}",
            f"Pending Inbox: {agent['pending_inbox']}",
            f"Final Response: {agent['final_response'] or '(none)'}",
        ]
        return ToolResult(tool_use_id=tool_use_id, content="\n".join(lines), is_error=False)

    return build_tool({
        "name": "AgentGet",
        "description": "Get details for one registered runtime agent.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Agent ID"},
            },
            "required": ["agent_id"],
        },
        "call": call,
        "is_concurrency_safe": lambda args: True,
        "is_read_only": lambda args: True,
    })


def create_agent_resume_tool() -> Tool:
    async def call(
        args: dict,
        context: "ToolUseContext",
        can_use_tool: Callable,
        on_progress: Callable | None = None,
    ) -> ToolResult:
        tool_use_id = args.get("tool_use_id", "")
        agent_id = args.get("agent_id", "")
        if not agent_id:
            return ToolResult(tool_use_id=tool_use_id, content="Error: agent_id is required", is_error=True)

        runtime = AgentRuntime.get_instance()
        agent = runtime.get_agent(agent_id)
        if agent is None:
            return ToolResult(tool_use_id=tool_use_id, content=f"Error: Agent not found: {agent_id}", is_error=True)
        if not hasattr(agent, "resume_background"):
            return ToolResult(
                tool_use_id=tool_use_id,
                content=f"Error: Agent does not support background resume: {agent_id}",
                is_error=True,
            )

        try:
            await agent.resume_background()
        except RuntimeError as exc:
            return ToolResult(
                tool_use_id=tool_use_id,
                content=str(exc),
                is_error=True,
            )
        return ToolResult(
            tool_use_id=tool_use_id,
            content=f"Resumed agent {agent_id}",
            is_error=False,
        )

    return build_tool({
        "name": "AgentResume",
        "description": "Resume a paused background agent by agent ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Agent ID"},
            },
            "required": ["agent_id"],
        },
        "call": call,
        "is_concurrency_safe": lambda args: True,
        "is_read_only": lambda args: False,
    })


def create_task_stop_tool() -> Tool:
    async def call(
        args: dict,
        context: "ToolUseContext",
        can_use_tool: Callable,
        on_progress: Callable | None = None,
    ) -> ToolResult:
        tool_use_id = args.get("tool_use_id", "")
        task_id = args.get("task_id")
        agent_id = args.get("agent_id")

        tracker = BackgroundTaskTracker.get_instance()
        state = None
        if task_id:
            state = tracker.get_state(task_id)
        elif agent_id:
            state = next((s for s in tracker.list_states() if getattr(s, "agent_id", None) == agent_id), None)
        else:
            return ToolResult(tool_use_id=tool_use_id, content="Error: task_id or agent_id is required", is_error=True)

        if state is None:
            return ToolResult(tool_use_id=tool_use_id, content="Error: Task not found", is_error=True)

        runtime = AgentRuntime.get_instance()
        target_agent_id = getattr(state, "agent_id", None) or agent_id
        agent = runtime.get_agent(target_agent_id) if target_agent_id else None
        if agent is None:
            return ToolResult(
                tool_use_id=tool_use_id,
                content=f"Error: Agent not found for task {state.id}",
                is_error=True,
            )

        await agent.stop()
        tracker.update_state_for_agent(
            target_agent_id,
            status=AgentStatus.STOPPED.value,
            completed_at=time.time(),
        )

        return ToolResult(
            tool_use_id=tool_use_id,
            content=f"Stopped task {state.id} ({state.subject})",
            is_error=False,
        )

    return build_tool({
        "name": "TaskStop",
        "description": "Stop a running background task or agent.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Background task ID"},
                "agent_id": {"type": "string", "description": "Background agent ID"},
            },
        },
        "call": call,
        "is_concurrency_safe": lambda args: True,
        "is_read_only": lambda args: False,
    })


def create_task_output_tool() -> Tool:
    async def call(
        args: dict,
        context: "ToolUseContext",
        can_use_tool: Callable,
        on_progress: Callable | None = None,
    ) -> ToolResult:
        tool_use_id = args.get("tool_use_id", "")
        task_id = args.get("task_id", "")
        if not task_id:
            return ToolResult(tool_use_id=tool_use_id, content="Error: task_id is required", is_error=True)

        tracker = BackgroundTaskTracker.get_instance()
        state = tracker.get_state(task_id)
        if state is None:
            return ToolResult(tool_use_id=tool_use_id, content=f"Error: Task not found: {task_id}", is_error=True)

        lines = [
            f"Task ID: {state.id}",
            f"Type: {state.task_type.value}",
            f"Status: {state.status}",
            f"Subject: {state.subject}",
            f"Description: {state.description or '(none)'}",
            f"Result: {state.result or '(none)'}",
        ]
        if state.error:
            lines.append(f"Error: {state.error}")
        if getattr(state, "agent_id", None):
            lines.append(f"Agent ID: {state.agent_id}")
        return ToolResult(
            tool_use_id=tool_use_id,
            content="\n".join(lines),
            is_error=False,
        )

    return build_tool({
        "name": "TaskOutput",
        "description": "Get the current output/result for a tracked background task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Tracked task ID"},
            },
            "required": ["task_id"],
        },
        "call": call,
        "is_concurrency_safe": lambda args: True,
        "is_read_only": lambda args: True,
    })
