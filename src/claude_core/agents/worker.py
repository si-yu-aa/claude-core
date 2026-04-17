"""WorkerAgent implementation."""

from __future__ import annotations

import asyncio
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
    from claude_core.tasks.types import BackgroundTaskTracker

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
        # Session sharing - must be set before _create_subagent_context() is called
        self._session_sharing_enabled = True
        self.context = self._create_subagent_context()
        self.status = AgentStatus.IDLE
        self._messages: list["Message"] = []
        self._final_response: str = ""
        self._engine: QueryEngine | None = None
        # Background task tracking
        self._background_task: asyncio.Task | None = None
        # Inherited messages from parent session
        self._inherited_messages: list["Message"] = []

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

        # Get tools from parent context
        parent_tools = []
        if hasattr(self.parent_context, 'options') and hasattr(self.parent_context.options, 'tools'):
            parent_tools = self.parent_context.options.tools or []

        # Get debug flag from parent context
        debug = False
        if hasattr(self.parent_context, 'options') and hasattr(self.parent_context.options, 'debug'):
            debug = self.parent_context.options.debug

        # Get main_loop_model from parent context
        main_loop_model = "gpt-4o"
        if hasattr(self.parent_context, 'options') and hasattr(self.parent_context.options, 'main_loop_model'):
            main_loop_model = self.parent_context.options.main_loop_model

        # Inherit messages from parent session if session sharing is enabled
        # This allows child agents to see the parent's conversation history
        inherited_messages = []
        if self._session_sharing_enabled and hasattr(self.parent_context, 'messages'):
            parent_messages = self.parent_context.messages
            if parent_messages and isinstance(parent_messages, list):
                # Only inherit a copy of messages for the child context
                inherited_messages = list(parent_messages)

        return ToolUseContext(
            options=ToolUseContextOptions(
                tools=parent_tools,
                debug=debug,
                main_loop_model=self.config.model or main_loop_model,
            ),
            abort_controller=abort_controller,
            agent_id=self.agent_id,
            messages=inherited_messages,
            query_tracking=query_tracking,
            # Pass API config for subagent to use
            base_url=getattr(self.parent_context, 'base_url', None),
            api_key=getattr(self.parent_context, 'api_key', None),
        )

    def _create_engine_config(self) -> QueryEngineConfig:
        """Create QueryEngine config from inherited context or environment."""
        base_url = getattr(self.context, 'base_url', None) or getattr(self.parent_context, 'base_url', None)
        api_key = getattr(self.context, 'api_key', None) or getattr(self.parent_context, 'api_key', None)

        if not base_url:
            base_url = "https://api.openai.com/v1"
        if not api_key:
            api_key = os.environ.get("OPENAI_API_KEY", "")

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

    async def start_background(self, task: str) -> str:
        """Start the agent running in the background without blocking.

        This launches the agent's task execution as an asyncio background task,
        allowing the caller to continue without waiting for completion.

        Args:
            task: The task description

        Returns:
            str: The agent_id of the background agent

        Note:
            Use get_background_status() to query the agent's state
            Use resume_background() to resume a paused agent
        """
        if self.status == AgentStatus.RUNNING and self._background_task:
            # Already running in background
            return self.agent_id

        self.status = AgentStatus.RUNNING
        self._messages = []
        self._final_response = ""

        # Add task as initial message
        task_msg = create_user_message(content=task)
        self._messages.append(task_msg)

        # Create the async task
        async def run_agent():
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

                self.status = AgentStatus.COMPLETED

            except asyncio.CancelledError:
                self.status = AgentStatus.STOPPED
                raise
            except Exception as e:
                self.status = AgentStatus.ERROR
                self._final_response = f"Error: {str(e)}"
                raise
            finally:
                self._engine = None

        self._background_task = asyncio.create_task(run_agent())
        return self.agent_id

    def get_background_status(self) -> dict:
        """Get the current status of a background agent.

        Returns:
            dict: Status information containing:
                - agent_id: The agent's unique ID
                - status: Current AgentStatus value
                - is_running: Whether the agent task is currently executing
                - is_done: Whether the agent task has completed
                - final_response: The agent's final response if completed
                - message_count: Number of messages processed
        """
        is_done = self._background_task.done() if self._background_task else True
        is_running = self._background_task is not None and not is_done

        return {
            "agent_id": self.agent_id,
            "status": self.status.value,
            "is_running": is_running,
            "is_done": is_done,
            "final_response": self._final_response if is_done else None,
            "message_count": len(self._messages),
        }

    async def resume_background(self) -> None:
        """Resume a paused/stopped background agent.

        For paused agents: Resumes the agent's execution from where it left off.
        For stopped agents: Cannot resume - use start_background() instead.
        For completed/error agents: Cannot resume - use start_background() instead.

        Raises:
            RuntimeError: If the agent cannot be resumed (not in paused state)
        """
        if self.status == AgentStatus.PAUSED:
            # Resume a paused agent
            self.status = AgentStatus.RUNNING
            # The abort controller was previously triggered by pause()
            # Create a new abort controller to allow execution to continue
            if hasattr(self.context, 'abort_controller'):
                # The child abort controller needs to be reset to allow continuation
                # But since it's linked to parent, we just set a new signal
                self.context.abort_controller.signal.aborted = False
                self.context.abort_controller.signal.reason = None
        elif self.status == AgentStatus.STOPPED:
            raise RuntimeError(
                f"Cannot resume stopped agent {self.agent_id}. "
                "Use start_background() to start a new background task."
            )
        elif self.status == AgentStatus.COMPLETED or self.status == AgentStatus.ERROR:
            raise RuntimeError(
                f"Cannot resume {self.status.value} agent {self.agent_id}. "
                "Use start_background() to start a new background task."
            )
        elif self.status == AgentStatus.IDLE:
            raise RuntimeError(
                f"Agent {self.agent_id} has not been started. "
                "Use start_background() to start a background task."
            )
        # If already RUNNING, nothing to do

    def disable_session_sharing(self) -> None:
        """Disable session sharing - child agent won't inherit parent messages."""
        self._session_sharing_enabled = False

    def enable_session_sharing(self) -> None:
        """Enable session sharing - child agent inherits parent messages."""
        self._session_sharing_enabled = True

    def get_session_sharing_status(self) -> bool:
        """Check if session sharing is enabled."""
        return self._session_sharing_enabled