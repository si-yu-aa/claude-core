"""AgentTool - spawn subagents via tool calls."""

from __future__ import annotations

import asyncio
from typing import Callable, Any, TYPE_CHECKING
import time

from claude_core.tools.base import Tool, ToolResult, build_tool
from claude_core.agents.types import AgentConfig, AgentStatus, AgentResult
from claude_core.agents.worker import WorkerAgent
from claude_core.tasks.types import (
    BackgroundTaskTracker,
    create_task_state,
    TaskType,
    TaskStatus,
    SubagentTaskState,
    BackgroundAgentTaskState,
)

if TYPE_CHECKING:
    from claude_core.models.tool import ToolUseContext


class BackgroundAgentTracker:
    """Legacy tracker for background agent tasks.

    This class is maintained for backwards compatibility.
    New code should use BackgroundTaskTracker from tasks/types.py directly.
    """

    _instance = None

    def __init__(self):
        self._agents: dict[str, asyncio.Task] = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def start(self, agent_id: str, task: asyncio.Task) -> None:
        self._agents[agent_id] = task

    def get_task(self, agent_id: str) -> asyncio.Task | None:
        return self._agents.get(agent_id)

    def is_running(self, agent_id: str) -> bool:
        task = self._agents.get(agent_id)
        return task is not None and not task.done()

    def remove(self, agent_id: str) -> None:
        if agent_id in self._agents:
            del self._agents[agent_id]


def create_agent_tool() -> Tool:
    """Create the AgentTool."""

    async def call(
        args: dict,
        context: "ToolUseContext",
        can_use_tool: Callable,
        on_progress: Callable | None = None,
    ) -> ToolResult:
        tool_use_id = args.get("tool_use_id", "")
        prompt = args.get("prompt", "")
        description = args.get("description", "")
        model = args.get("model", None)
        run_in_background = args.get("run_in_background", False)

        if not prompt:
            return ToolResult(
                tool_use_id=tool_use_id,
                content="Error: prompt is required",
                is_error=True,
            )

        # Get tools from context
        tools = []
        if hasattr(context, 'options') and hasattr(context.options, 'tools'):
            tools = context.options.tools or []

        # Get agent_id from context for tracking
        parent_agent_id = getattr(context, 'agent_id', None)

        # Create agent config
        config = AgentConfig(
            name="subagent",
            description=description or f"Agent for: {prompt[:50]}...",
            system_prompt="You are a helpful assistant.",
            tools=tools,
            model=model,
            max_turns=None,
        )

        # Create worker agent with parent context
        agent = WorkerAgent(
            config=config,
            parent_context=context,
        )

        # Get the background task tracker
        tracker = BackgroundTaskTracker.get_instance()

        if run_in_background:
            # Create task state for background agent
            task_state = create_task_state(
                task_type=TaskType.BACKGROUND_AGENT,
                subject=description or prompt[:50],
                description=f"Background agent for: {prompt}",
                owner=parent_agent_id,
                agent_id=agent.agent_id,
                agent_name=config.name,
                model=model or "default",
                is_backgrounded=True,
            )
            tracker.add_state(task_state)
            task_state.status = TaskStatus.RUNNING.value
            task_state.started_at = time.time()

            await agent.start_background(prompt)
            task = getattr(agent, "_background_task", None)
            if task is not None:
                tracker.start_task(agent.agent_id, task)

                def _sync_state(done_task: asyncio.Task) -> None:
                    task_state.status = getattr(agent.status, "value", str(agent.status))
                    task_state.completed_at = time.time()
                    task_state.result = getattr(agent, "_final_response", "") or None
                    if done_task.cancelled():
                        task_state.error = "cancelled"
                    else:
                        exc = done_task.exception()
                        if exc is not None:
                            task_state.error = str(exc)

                task.add_done_callback(_sync_state)

            return ToolResult(
                tool_use_id=tool_use_id,
                content=(
                    f"Background agent started\n"
                    f"task_id: {task_state.id}\n"
                    f"agent_id: {agent.agent_id}"
                ),
                is_error=False,
            )
        else:
            # Create task state for foreground subagent
            task_state = create_task_state(
                task_type=TaskType.SUBAGENT,
                subject=description or prompt[:50],
                description=f"Subagent for: {prompt}",
                owner=parent_agent_id,
                agent_id=agent.agent_id,
                agent_name=config.name,
                model=model or "default",
                prompt=prompt,
                run_in_background=False,
            )
            tracker.add_state(task_state)
            task_state.status = "running"
            task_state.started_at = time.time()

            try:
                result = await agent.run(prompt)
                task_state.status = result.status.value
                task_state.completed_at = time.time()
                task_state.result = result.final_response

                status_str = result.status.value if result.status else "completed"
                content = f"[Agent: {result.agent_id}] {status_str}\n\n{result.final_response}"
                return ToolResult(
                    tool_use_id=tool_use_id,
                    content=content,
                    is_error=(result.status == AgentStatus.ERROR),
                )
            except Exception as e:
                task_state.status = "failed"
                task_state.error = str(e)
                task_state.completed_at = time.time()
                return ToolResult(
                    tool_use_id=tool_use_id,
                    content=f"Error running agent: {str(e)}",
                    is_error=True,
                )

    def is_concurrency_safe(args: dict) -> bool:
        return False

    def is_read_only(args: dict) -> bool:
        return False

    def is_destructive(args: dict) -> bool:
        return True

    def interrupt_behavior() -> str:
        return "cancel"

    return build_tool({
        "name": "Agent",
        "description": "Launch a new agent to accomplish a task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The task for the agent to accomplish",
                },
                "description": {
                    "type": "string",
                    "description": "Optional description of the task",
                },
                "model": {
                    "type": "string",
                    "description": "Optional model override",
                },
                "run_in_background": {
                    "type": "boolean",
                    "description": "Run in background",
                    "default": False,
                },
            },
            "required": ["prompt"],
        },
        "call": call,
        "is_concurrency_safe": is_concurrency_safe,
        "is_read_only": is_read_only,
        "is_destructive": is_destructive,
        "interrupt_behavior": interrupt_behavior,
        "aliases": ["AgentTool", "Subagent", "SpawnAgent"],
        "searchHint": "agent subagent spawn fork run",
    })
