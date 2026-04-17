"""WorkerAgent implementation."""

from __future__ import annotations

import os
from typing import Any, Optional, TYPE_CHECKING

from claude_core.agents.base import BaseAgent
from claude_core.agents.types import AgentConfig, AgentStatus, AgentResult, ForkContext
from claude_core.agents.mailbox import Mailbox
from claude_core.utils.uuid import generate_agent_id
from claude_core.utils.abort import AbortController, create_child_abort_controller
from claude_core.engine.query_engine import QueryEngine
from claude_core.engine.config import QueryEngineConfig
from claude_core.models.message import create_user_message
from claude_core.models.tool import QueryChainTracking

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
    5. Abort controller integration
    6. Pause/resume state machine
    """

    def __init__(
        self,
        config: AgentConfig,
        parent_context: Any,
        fork_context: ForkContext | None = None,
    ):
        super().__init__(config)
        self._agent_id = generate_agent_id()
        self.parent_context = parent_context
        self.fork_context = fork_context or ForkContext(
            chain_id=self._agent_id,
            depth=0,
        )
        self.context = self._create_subagent_context()
        self.status = AgentStatus.IDLE
        self._messages: list["Message"] = []
        self._final_response: str = ""
        self._engine: QueryEngine | None = None

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

        # Create query chain tracking with incremented depth
        parent_tracking = None
        if hasattr(self.parent_context, 'query_tracking') and self.parent_context.query_tracking:
            parent_tracking = self.parent_context.query_tracking

        if parent_tracking:
            query_tracking = QueryChainTracking(
                chain_id=parent_tracking.chain_id,
                depth=parent_tracking.depth + 1,
            )
        else:
            query_tracking = QueryChainTracking(
                chain_id=self.fork_context.chain_id,
                depth=self.fork_context.depth,
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
            query_tracking=query_tracking,
        )

    def _create_engine_config(self) -> QueryEngineConfig:
        """Create QueryEngine config from parent context or defaults."""
        # Try to get config from parent context if available
        base_url = getattr(self.parent_context, 'base_url', None) or "https://api.openai.com/v1"
        api_key = getattr(self.parent_context, 'api_key', None) or os.environ.get("OPENAI_API_KEY", "test-key")

        return QueryEngineConfig(
            api_key=api_key,
            model=self.config.model or "gpt-4o",
            base_url=base_url,
            max_turns=self.config.max_turns,
        )

    async def run(self, task: str) -> AgentResult:
        """
        Run the worker agent to execute a task using QueryEngine.

        Args:
            task: The task description

        Returns:
            AgentResult with execution results
        """
        self.status = AgentStatus.RUNNING
        self._messages = []
        self._final_response = ""

        # Add task as initial message
        task_msg = create_user_message(content=task)
        self._messages.append(task_msg)

        try:
            # Create QueryEngine with agent's config
            config = self._create_engine_config()
            engine = QueryEngine(config)
            self._engine = engine

            # Set up engine with context
            engine.set_system_prompt(self.config.system_prompt)
            engine.set_tools(self.config.tools)
            engine.set_tool_use_context(self.context)

            # Set can_use_tool callback from parent if available
            if hasattr(self.parent_context, 'can_use_tool'):
                engine.set_can_use_tool(self.parent_context.can_use_tool)

            # Execute query and collect results
            async for event in engine.submit_message(task):
                if isinstance(event, dict):
                    event_type = event.get("type")
                    if event_type == "message" and event.get("message"):
                        self._messages.append(event["message"])
                    elif event_type == "content":
                        self._final_response += event.get("content", "")
                    elif event_type == "error":
                        raise RuntimeError(event.get("error", "Unknown error"))

            return AgentResult(
                agent_id=self.agent_id,
                messages=self._messages,
                final_response=self._final_response or "Task completed.",
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
        finally:
            self._engine = None

    async def stop(self) -> None:
        """Stop the worker agent."""
        self.status = AgentStatus.STOPPED
        if hasattr(self.context, 'abort_controller'):
            self.context.abort_controller.abort("agent_stop")
        if self._engine:
            self._engine.stop()

    async def pause(self) -> None:
        """Pause the agent using state machine."""
        if self.status == AgentStatus.RUNNING:
            self.status = AgentStatus.PAUSED
            if hasattr(self.context, 'abort_controller'):
                self.context.abort_controller.abort("agent_pause")

    async def resume(self) -> None:
        """Resume a paused agent."""
        if self.status == AgentStatus.PAUSED:
            self.status = AgentStatus.RUNNING