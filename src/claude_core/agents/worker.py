"""WorkerAgent implementation."""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING
from dataclasses import dataclass

from claude_core.agents.base import BaseAgent
from claude_core.agents.types import AgentConfig, AgentStatus, AgentResult
from claude_core.agents.mailbox import Mailbox
from claude_core.utils.uuid import generate_agent_id
from claude_core.utils.abort import AbortController, create_child_abort_controller

if TYPE_CHECKING:
    from claude_core.models.message import Message

class WorkerAgent(BaseAgent):
    """
    Worker Agent - used for sub-task delegation.

    Key features:
    1. Independent tool_use_context
    2. Nested query tracking (chainId + depth)
    3. Message mailbox mechanism
    4. Lifecycle management
    """

    def __init__(
        self,
        config: AgentConfig,
        parent_context: Any,
    ):
        super().__init__(config)
        self._agent_id = generate_agent_id()
        self.parent_context = parent_context
        self.context = self._create_subagent_context()
        self.status = AgentStatus.IDLE
        self._messages: list["Message"] = []

    @property
    def agent_id(self) -> str:
        """Get the agent's unique ID."""
        return self._agent_id

    def _create_subagent_context(self) -> Any:
        """Create a sub-agent context from parent context."""
        from claude_core.models.tool import ToolUseContext, ToolUseContextOptions

        # Create child abort controller
        abort_controller = create_child_abort_controller(
            self.parent_context.abort_controller
        )

        return ToolUseContext(
            options=ToolUseContextOptions(
                tools=self.config.tools,
                debug=self.parent_context.options.debug,
                main_loop_model=self.config.model or self.parent_context.options.main_loop_model,
            ),
            abort_controller=abort_controller,
            agent_id=self.agent_id,
            messages=[],
        )

    async def run(self, task: str) -> AgentResult:
        """
        Run the worker agent to execute a task.

        Args:
            task: The task description

        Returns:
            AgentResult with execution results
        """
        from claude_core.models.message import create_user_message

        self.status = AgentStatus.RUNNING
        self._messages = []

        # Add task as initial message
        task_msg = create_user_message(content=task)
        self._messages.append(task_msg)

        try:
            # In a full implementation, this would:
            # 1. Create a QueryEngine with the agent's config
            # 2. Run the query loop
            # 3. Collect results

            # For now, return a placeholder result
            final_response = f"Agent {self.config.name} processed task: {task}"

            return AgentResult(
                agent_id=self.agent_id,
                messages=self._messages,
                final_response=final_response,
                status=AgentStatus.COMPLETED,
            )

        except Exception as e:
            self.status = AgentStatus.ERROR
            return AgentResult(
                agent_id=self.agent_id,
                messages=self._messages,
                final_response=f"Error: {str(e)}",
                status=AgentStatus.ERROR,
            )

    async def stop(self) -> None:
        """Stop the worker agent."""
        self.status = AgentStatus.STOPPED
        if hasattr(self.context, 'abort_controller'):
            self.context.abort_controller.abort("agent_stop")

    async def pause(self) -> None:
        """Pause the agent."""
        # Pause implementation
        pass

    async def resume(self) -> None:
        """Resume a paused agent."""
        # Resume implementation
        pass