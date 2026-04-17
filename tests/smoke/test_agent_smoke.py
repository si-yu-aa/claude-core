"""Smoke tests for Agent system.

These tests verify the basic functionality of the agent system.
"""

import pytest
from unittest.mock import MagicMock
from claude_core.agents.base import BaseAgent
from claude_core.agents.types import AgentConfig, AgentStatus, AgentResult, ForkContext
from claude_core.agents.worker import WorkerAgent
from claude_core.tasks.types import (
    TaskType,
    TaskStatus,
    TaskState,
    create_task_id,
    create_task_state,
    BackgroundTaskTracker,
)


class TestAgentConfig:
    """Smoke tests for AgentConfig."""

    def test_agent_config_defaults(self):
        """Should have sensible defaults."""
        config = AgentConfig(
            name="test-agent",
            description="A test agent",
            system_prompt="You are helpful.",
        )
        assert config.name == "test-agent"
        assert config.description == "A test agent"
        assert config.max_turns is None

    def test_agent_config_with_tools(self):
        """Should accept tools."""
        config = AgentConfig(
            name="test-agent",
            description="A test agent",
            system_prompt="You are helpful.",
            tools=["Read", "Write"],
        )
        assert len(config.tools) == 2

    def test_agent_config_with_model(self):
        """Should accept model parameter."""
        config = AgentConfig(
            name="test-agent",
            description="A test agent",
            system_prompt="You are helpful.",
            model="gpt-4o",
        )
        assert config.model == "gpt-4o"


class TestAgentStatus:
    """Smoke tests for AgentStatus enum."""

    def test_all_statuses(self):
        """Should have all expected statuses."""
        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.RUNNING.value == "running"
        assert AgentStatus.PAUSED.value == "paused"
        assert AgentStatus.STOPPED.value == "stopped"
        assert AgentStatus.ERROR.value == "error"


class TestAgentResult:
    """Smoke tests for AgentResult."""

    def test_agent_result_creation(self):
        """Should create AgentResult."""
        result = AgentResult(
            agent_id="agent-123",
            messages=[],
            final_response="Done",
            status=AgentStatus.COMPLETED,
        )

        assert result.agent_id == "agent-123"
        assert result.final_response == "Done"
        assert result.status == AgentStatus.COMPLETED


class TestForkContext:
    """Smoke tests for ForkContext."""

    def test_fork_context_defaults(self):
        """Should have sensible defaults."""
        ctx = ForkContext(chain_id="default", depth=0)
        assert ctx.chain_id == "default"
        assert ctx.depth == 0

    def test_fork_context_custom(self):
        """Should accept custom values."""
        ctx = ForkContext(chain_id="custom-chain", depth=2)
        assert ctx.chain_id == "custom-chain"
        assert ctx.depth == 2


class TestWorkerAgentSmoke:
    """Smoke tests for WorkerAgent."""

    def test_worker_agent_initialization(self):
        """Should initialize WorkerAgent."""
        config = AgentConfig(
            name="test-worker",
            description="A test worker agent",
            system_prompt="You are helpful.",
        )

        # Create a mock parent context
        mock_parent = MagicMock()
        mock_parent.abort_controller = MagicMock()
        mock_parent.query_tracking = None

        agent = WorkerAgent(config=config, parent_context=mock_parent)

        assert agent.agent_id is not None
        assert agent.status == AgentStatus.IDLE

    def test_worker_agent_with_parent_tracking(self):
        """Should inherit parent query tracking."""
        from claude_core.models.tool import QueryChainTracking

        config = AgentConfig(
            name="test-worker",
            description="A test worker agent",
            system_prompt="You are helpful.",
        )

        mock_parent = MagicMock()
        mock_parent.abort_controller = MagicMock()
        mock_parent.query_tracking = QueryChainTracking(chain_id="parent-chain", depth=1)

        agent = WorkerAgent(config=config, parent_context=mock_parent)

        # Should increment depth
        assert agent.context.query_tracking.depth == 2
        assert agent.context.query_tracking.chain_id == "parent-chain"


class TestTaskState:
    """Smoke tests for TaskState types."""

    def test_create_task_id(self):
        """Should create unique task IDs."""
        ids = set()
        for _ in range(10):
            tid = create_task_id()
            assert tid not in ids
            ids.add(tid)

    def test_create_task_state_local_shell(self):
        """Should create LocalShellTaskState."""
        from claude_core.tasks.types import LocalShellTaskState

        state = create_task_state(
            task_type=TaskType.LOCAL_SHELL,
            subject="Run tests",
            command="pytest",
        )

        assert isinstance(state, LocalShellTaskState)
        assert state.command == "pytest"

    def test_create_task_state_subagent(self):
        """Should create SubagentTaskState."""
        from claude_core.tasks.types import SubagentTaskState

        state = create_task_state(
            task_type=TaskType.SUBAGENT,
            subject="Subagent task",
            agent_name="helper",
            run_in_background=True,
        )

        assert isinstance(state, SubagentTaskState)
        assert state.agent_name == "helper"
        assert state.run_in_background is True


class TestBackgroundTaskTracker:
    """Smoke tests for BackgroundTaskTracker."""

    def test_singleton(self):
        """Should be a singleton."""
        tracker1 = BackgroundTaskTracker.get_instance()
        tracker2 = BackgroundTaskTracker.get_instance()
        assert tracker1 is tracker2

    def test_add_and_get_state(self):
        """Should store and retrieve task state."""
        tracker = BackgroundTaskTracker()

        state = create_task_state(
            task_type=TaskType.LOCAL_AGENT,
            subject="Test",
        )
        tracker.add_state(state)

        assert tracker.get_state(state.id) is state

    def test_is_running(self):
        """Should correctly report running status."""
        tracker = BackgroundTaskTracker()

        # No task should not be running
        assert tracker.is_running("non-existent") is False
