import pytest
import time
import asyncio

from claude_core.agents.runtime import AgentRuntime
from claude_core.tasks.types import BackgroundTaskTracker, TaskStatus, TaskType, create_task_state
from claude_core.tools.builtin.runtime import (
    create_agent_get_tool,
    create_agent_list_tool,
    create_agent_resume_tool,
    create_send_message_tool,
    create_task_output_tool,
    create_task_stop_tool,
)
from claude_core.models.tool import ToolUseContext, ToolUseContextOptions
from claude_core.utils.abort import AbortController


@pytest.fixture
def context():
    AgentRuntime.get_instance().clear()
    BackgroundTaskTracker.get_instance().clear()
    ctx = ToolUseContext(
        options=ToolUseContextOptions(tools=[]),
        abort_controller=AbortController(),
        agent_id="lead-agent",
    )
    yield ctx
    AgentRuntime.get_instance().clear()
    BackgroundTaskTracker.get_instance().clear()


@pytest.mark.asyncio
async def test_send_message_tool_delivers_to_runtime_mailbox(context):
    runtime = AgentRuntime.get_instance()

    class Recipient:
        agent_id = "worker-1"

    runtime.register(Recipient())

    tool = create_send_message_tool()
    result = await tool.call(
        {
            "tool_use_id": "send-msg",
            "recipient_id": "worker-1",
            "message": "keep going",
        },
        context,
        lambda *args: True,
    )

    assert result.is_error is False
    queued = runtime.mailbox.receive("worker-1")
    assert queued is not None
    assert queued.sender_id == "lead-agent"
    assert queued.content == "keep going"


@pytest.mark.asyncio
async def test_task_stop_tool_stops_background_agent(context):
    runtime = AgentRuntime.get_instance()
    tracker = BackgroundTaskTracker.get_instance()

    class StoppableAgent:
        agent_id = "worker-stop"
        stopped = False

        async def stop(self):
            self.stopped = True

    agent = StoppableAgent()
    runtime.register(agent)
    state = create_task_state(
        task_type=TaskType.BACKGROUND_AGENT,
        subject="Long task",
        description="runtime controlled",
        agent_id=agent.agent_id,
        agent_name="worker",
        model="gpt-4o",
        is_backgrounded=True,
    )
    state.status = TaskStatus.RUNNING.value
    state.started_at = time.time()
    tracker.add_state(state)

    tool = create_task_stop_tool()
    result = await tool.call(
        {
            "tool_use_id": "stop-task",
            "task_id": state.id,
        },
        context,
        lambda *args: True,
    )

    assert result.is_error is False
    assert agent.stopped is True
    assert state.status == "stopped"
    assert state.completed_at is not None


@pytest.mark.asyncio
async def test_task_stop_tool_removes_tracker_task_handle(context):
    runtime = AgentRuntime.get_instance()
    tracker = BackgroundTaskTracker.get_instance()

    class StoppableAgent:
        agent_id = "worker-stop-handle"

        async def stop(self):
            return None

    agent = StoppableAgent()
    runtime.register(agent)
    state = create_task_state(
        task_type=TaskType.BACKGROUND_AGENT,
        subject="Long task",
        description="runtime controlled",
        agent_id=agent.agent_id,
        agent_name="worker",
        model="gpt-4o",
        is_backgrounded=True,
    )
    state.status = TaskStatus.RUNNING.value
    state.started_at = time.time()
    tracker.add_state(state)
    tracker.start_task(agent.agent_id, asyncio.create_task(asyncio.sleep(60)))

    tool = create_task_stop_tool()
    result = await tool.call(
        {
            "tool_use_id": "stop-task-handle",
            "task_id": state.id,
        },
        context,
        lambda *args: True,
    )

    assert result.is_error is False
    assert tracker.get_task(agent.agent_id) is None


@pytest.mark.asyncio
async def test_task_stop_tool_unregisters_stopped_agent(context):
    runtime = AgentRuntime.get_instance()
    tracker = BackgroundTaskTracker.get_instance()

    class StoppableAgent:
        agent_id = "worker-stop-runtime"

        async def stop(self):
            runtime.unregister(self.agent_id)

    agent = StoppableAgent()
    runtime.register(agent)
    state = create_task_state(
        task_type=TaskType.BACKGROUND_AGENT,
        subject="Long task",
        description="runtime unregister",
        agent_id=agent.agent_id,
        agent_name="worker",
        model="gpt-4o",
        is_backgrounded=True,
    )
    state.status = TaskStatus.RUNNING.value
    state.started_at = time.time()
    tracker.add_state(state)

    tool = create_task_stop_tool()
    result = await tool.call(
        {
            "tool_use_id": "stop-task-runtime",
            "task_id": state.id,
        },
        context,
        lambda *args: True,
    )

    assert result.is_error is False
    assert runtime.get_agent(agent.agent_id) is None


@pytest.mark.asyncio
async def test_agent_list_tool_reports_registered_agents(context):
    runtime = AgentRuntime.get_instance()

    class ListedAgent:
        agent_id = "worker-list"

        def __init__(self):
            self.status = type("Status", (), {"value": "running"})()
            self._messages = ["a", "b"]
            self._final_response = "in progress"

    runtime.register(ListedAgent())
    runtime.mailbox.send("lead-agent", "worker-list", "queued work")

    tool = create_agent_list_tool()
    result = await tool.call(
        {"tool_use_id": "agent-list"},
        context,
        lambda *args: True,
    )

    assert result.is_error is False
    assert "worker-list" in result.content
    assert "running" in result.content
    assert "inbox=1" in result.content


@pytest.mark.asyncio
async def test_agent_get_tool_reports_agent_details(context):
    runtime = AgentRuntime.get_instance()

    class DetailedAgent:
        agent_id = "worker-get"

        def __init__(self):
            self.status = type("Status", (), {"value": "paused"})()
            self._messages = ["msg"]
            self._final_response = "waiting"

    runtime.register(DetailedAgent())
    runtime.mailbox.send("lead-agent", "worker-get", "queued detail")

    tool = create_agent_get_tool()
    result = await tool.call(
        {
            "tool_use_id": "agent-get",
            "agent_id": "worker-get",
        },
        context,
        lambda *args: True,
    )

    assert result.is_error is False
    assert "worker-get" in result.content
    assert "paused" in result.content
    assert "waiting" in result.content
    assert "Pending Inbox: 1" in result.content


@pytest.mark.asyncio
async def test_send_message_tool_resumes_paused_agent(context):
    runtime = AgentRuntime.get_instance()
    called = {}

    class PausedAgent:
        agent_id = "worker-paused"

        def __init__(self):
            self.status = type("Status", (), {"value": "paused"})()

        async def resume_background(self):
            called["resumed"] = True

    runtime.register(PausedAgent())

    tool = create_send_message_tool()
    result = await tool.call(
        {
            "tool_use_id": "send-resume",
            "recipient_id": "worker-paused",
            "message": "continue please",
        },
        context,
        lambda *args: True,
    )

    assert result.is_error is False
    assert called["resumed"] is True


@pytest.mark.asyncio
async def test_send_message_tool_rejects_stopped_agent(context):
    runtime = AgentRuntime.get_instance()

    class StoppedAgent:
        agent_id = "worker-stopped"

        def __init__(self):
            self.status = type("Status", (), {"value": "stopped"})()

    runtime.register(StoppedAgent())

    tool = create_send_message_tool()
    result = await tool.call(
        {
            "tool_use_id": "send-stopped",
            "recipient_id": "worker-stopped",
            "message": "continue please",
        },
        context,
        lambda *args: True,
    )

    assert result.is_error is True
    assert runtime.mailbox.pending_count("worker-stopped") == 0


@pytest.mark.asyncio
async def test_task_output_tool_reports_task_result(context):
    tracker = BackgroundTaskTracker.get_instance()
    state = create_task_state(
        task_type=TaskType.BACKGROUND_AGENT,
        subject="Background summarize",
        description="collect result",
        agent_id="worker-output",
        agent_name="worker",
        model="gpt-4o",
        is_backgrounded=True,
    )
    state.status = TaskStatus.COMPLETED.value
    state.result = "final answer"
    tracker.add_state(state)

    tool = create_task_output_tool()
    result = await tool.call(
        {
            "tool_use_id": "task-output",
            "task_id": state.id,
        },
        context,
        lambda *args: True,
    )

    assert result.is_error is False
    assert state.id in result.content
    assert "final answer" in result.content
    assert "completed" in result.content


@pytest.mark.asyncio
async def test_agent_resume_tool_resumes_agent(context):
    runtime = AgentRuntime.get_instance()
    called = {}

    class ResumableAgent:
        agent_id = "worker-resume"

        def __init__(self):
            self.status = type("Status", (), {"value": "paused"})()

        async def resume_background(self):
            called["resumed"] = True

    runtime.register(ResumableAgent())

    tool = create_agent_resume_tool()
    result = await tool.call(
        {
            "tool_use_id": "agent-resume",
            "agent_id": "worker-resume",
        },
        context,
        lambda *args: True,
    )

    assert result.is_error is False
    assert called["resumed"] is True


@pytest.mark.asyncio
async def test_agent_resume_tool_returns_error_when_resume_fails(context):
    runtime = AgentRuntime.get_instance()

    class StoppedAgent:
        agent_id = "worker-resume-stopped"

        def __init__(self):
            self.status = type("Status", (), {"value": "stopped"})()

        async def resume_background(self):
            raise RuntimeError("Cannot resume stopped agent worker-resume-stopped")

    runtime.register(StoppedAgent())

    tool = create_agent_resume_tool()
    result = await tool.call(
        {
            "tool_use_id": "agent-resume-error",
            "agent_id": "worker-resume-stopped",
        },
        context,
        lambda *args: True,
    )

    assert result.is_error is True
    assert "Cannot resume stopped agent" in result.content
