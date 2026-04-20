import pytest
import asyncio
import time
from claude_core.agents.worker import WorkerAgent
from claude_core.agents.types import AgentConfig, AgentStatus, AgentResult, ForkContext
from claude_core.agents.runtime import AgentRuntime
from claude_core.utils.abort import AbortController
from claude_core.models.tool import QueryChainTracking, ToolPermissionContext
from claude_core.tasks.types import BackgroundTaskTracker, TaskStatus, TaskType, create_task_state

@pytest.fixture
def agent_config():
    return AgentConfig(
        name="TestAgent",
        description="A test agent",
        system_prompt="You are a helpful test agent.",
        tools=[],
        model="gpt-4o",
        max_turns=10,
    )

@pytest.fixture
def parent_context():
    from claude_core.models.tool import ToolUseContext, ToolUseContextOptions
    return ToolUseContext(
        options=ToolUseContextOptions(tools=[]),
        abort_controller=AbortController(),
    )

@pytest.fixture
def fork_context():
    return ForkContext(chain_id="test-chain", depth=0)

def test_agent_config_creation(agent_config):
    assert agent_config.name == "TestAgent"
    assert agent_config.model == "gpt-4o"
    assert agent_config.max_turns == 10

def test_agent_status_enum():
    from claude_core.agents.types import AgentStatus
    assert AgentStatus.IDLE.value == "idle"
    assert AgentStatus.RUNNING.value == "running"
    assert AgentStatus.PAUSED.value == "paused"
    assert AgentStatus.STOPPED.value == "stopped"

@pytest.mark.asyncio
async def test_worker_agent_initialization(agent_config, parent_context):
    agent = WorkerAgent(config=agent_config, parent_context=parent_context)
    assert agent.agent_id.startswith("agent_")
    assert agent.status == AgentStatus.IDLE
    assert agent.config == agent_config

@pytest.mark.asyncio
async def test_worker_agent_with_fork_context(agent_config, parent_context, fork_context):
    agent = WorkerAgent(config=agent_config, parent_context=parent_context, fork_context=fork_context)
    assert agent.fork_context == fork_context
    assert agent.fork_context.chain_id == "test-chain"
    assert agent.fork_context.depth == 0

@pytest.mark.asyncio
async def test_worker_agent_query_tracking(agent_config, parent_context):
    agent = WorkerAgent(config=agent_config, parent_context=parent_context)
    # Should have query tracking set up
    assert agent.context.query_tracking is not None
    assert agent.context.query_tracking.chain_id == agent.agent_id
    assert agent.context.query_tracking.depth == 0

@pytest.mark.asyncio
async def test_worker_agent_child_abort_controller(agent_config, parent_context):
    agent = WorkerAgent(config=agent_config, parent_context=parent_context)
    # Child abort controller should be created
    assert agent.context.abort_controller is not None
    # Should be linked to parent
    parent_abort = parent_context.abort_controller
    child_abort = agent.context.abort_controller
    assert child_abort is not parent_abort

@pytest.mark.asyncio
async def test_worker_agent_pause_resume(agent_config, parent_context):
    agent = WorkerAgent(config=agent_config, parent_context=parent_context)
    assert agent.status == AgentStatus.IDLE

    # Can't pause if not running
    await agent.pause()
    assert agent.status == AgentStatus.IDLE

    # Start the agent (simulate running state)
    agent.status = AgentStatus.RUNNING
    await agent.pause()
    assert agent.status == AgentStatus.PAUSED

    # Resume
    await agent.resume()
    assert agent.status == AgentStatus.RUNNING


@pytest.mark.asyncio
async def test_worker_agent_pause_does_not_abort_parent_context(agent_config, parent_context):
    agent = WorkerAgent(config=agent_config, parent_context=parent_context)
    agent.status = AgentStatus.RUNNING

    await agent.pause()

    assert agent.status == AgentStatus.PAUSED
    assert parent_context.abort_controller.signal.aborted is False


@pytest.mark.asyncio
async def test_worker_agent_stop_does_not_abort_parent_context(agent_config, parent_context):
    agent = WorkerAgent(config=agent_config, parent_context=parent_context)
    agent.status = AgentStatus.RUNNING

    await agent.stop()

    assert agent.status == AgentStatus.STOPPED
    assert parent_context.abort_controller.signal.aborted is False

@pytest.mark.asyncio
async def test_worker_agent_stop(agent_config, parent_context):
    agent = WorkerAgent(config=agent_config, parent_context=parent_context)
    agent.status = AgentStatus.RUNNING

    await agent.stop()
    assert agent.status == AgentStatus.STOPPED

@pytest.mark.asyncio
async def test_fork_context_dataclass():
    ctx = ForkContext(chain_id="chain-123", depth=2)
    assert ctx.chain_id == "chain-123"
    assert ctx.depth == 2

def test_agent_result_dataclass():
    from claude_core.models.message import create_user_message
    msg = create_user_message(content="test")
    result = AgentResult(
        agent_id="agent_test",
        messages=[msg],
        final_response="Test response",
        status=AgentStatus.COMPLETED,
    )
    assert result.agent_id == "agent_test"
    assert len(result.messages) == 1
    assert result.final_response == "Test response"
    assert result.status == AgentStatus.COMPLETED


@pytest.mark.asyncio
async def test_worker_agent_inherits_parent_api_config(agent_config, parent_context):
    parent_context.base_url = "https://example.test/v1"
    parent_context.api_key = "parent-key"

    agent = WorkerAgent(config=agent_config, parent_context=parent_context)

    engine_config = agent._create_engine_config()
    assert engine_config.base_url == "https://example.test/v1"
    assert engine_config.api_key == "parent-key"


@pytest.mark.asyncio
async def test_worker_agent_inherits_provider_and_runtime_context(agent_config, parent_context):
    parent_context.base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
    parent_context.api_key = "gemini-key"
    parent_context.options.mcp_clients = ["mcp-client"]
    parent_context.options.permission_context = ToolPermissionContext(deny_rules=["bash:exec"])
    parent_context.options.task_store_path = "/tmp/test-tasks.json"
    parent_context.options.main_loop_model = "gemini-2.5-pro"
    parent_context.provider = "gemini"

    agent = WorkerAgent(config=agent_config, parent_context=parent_context)

    assert agent.context.options.mcp_clients == ["mcp-client"]
    assert agent.context.options.permission_context is parent_context.options.permission_context
    assert agent.context.options.task_store_path == "/tmp/test-tasks.json"

    engine_config = agent._create_engine_config()
    assert engine_config.provider == "gemini"
    assert engine_config.base_url == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert engine_config.api_key == "gemini-key"


@pytest.mark.asyncio
async def test_worker_agent_start_background_returns_agent_id(agent_config, parent_context):
    """Test that start_background returns the agent_id without blocking."""
    agent = WorkerAgent(config=agent_config, parent_context=parent_context)

    # start_background should return immediately with agent_id
    result = await agent.start_background("Test task")
    assert result == agent.agent_id
    assert agent.status == AgentStatus.RUNNING

    # Clean up
    await agent.stop()


@pytest.mark.asyncio
async def test_worker_agent_background_processes_mailbox_messages(agent_config, parent_context, monkeypatch):
    runtime = AgentRuntime.get_instance()
    runtime.clear()
    submitted_prompts = []

    class FakeEngine:
        def __init__(self, config):
            self.config = config

        def set_system_prompt(self, prompt):
            self.prompt = prompt

        def set_tools(self, tools):
            self.tools = tools

        def set_tool_use_context(self, context):
            self.context = context

        def set_can_use_tool(self, can_use_tool):
            self.can_use_tool = can_use_tool

        async def submit_message(self, prompt):
            submitted_prompts.append(prompt)
            yield {"type": "content", "content": f"done:{prompt}"}

        def stop(self):
            return None

    monkeypatch.setattr("claude_core.agents.worker.QueryEngine", FakeEngine)

    agent = WorkerAgent(config=agent_config, parent_context=parent_context)
    await agent.start_background("initial task")

    runtime.mailbox.send("lead", agent.agent_id, "follow-up task")
    await asyncio.sleep(0.2)
    await agent.stop()

    assert submitted_prompts[:2] == ["initial task", "follow-up task"]


@pytest.mark.asyncio
async def test_worker_agent_background_pause_resume_keeps_task_alive(agent_config, parent_context, monkeypatch):
    runtime = AgentRuntime.get_instance()
    runtime.clear()
    submitted_prompts = []

    class FakeEngine:
        def __init__(self, config):
            self.config = config

        def set_system_prompt(self, prompt):
            self.prompt = prompt

        def set_tools(self, tools):
            self.tools = tools

        def set_tool_use_context(self, context):
            self.context = context

        def set_can_use_tool(self, can_use_tool):
            self.can_use_tool = can_use_tool

        async def submit_message(self, prompt):
            submitted_prompts.append(prompt)
            yield {"type": "content", "content": f"done:{prompt}"}

        def stop(self):
            return None

    monkeypatch.setattr("claude_core.agents.worker.QueryEngine", FakeEngine)

    agent = WorkerAgent(config=agent_config, parent_context=parent_context)
    await agent.start_background("initial task")
    await asyncio.sleep(0.1)

    await agent.pause()
    assert agent.status == AgentStatus.PAUSED
    assert agent._background_task is not None
    assert agent._background_task.done() is False
    assert parent_context.abort_controller.signal.aborted is False

    await agent.resume_background()
    runtime.mailbox.send("lead", agent.agent_id, "resumed task")
    await asyncio.sleep(0.2)
    await agent.stop()

    assert submitted_prompts[:2] == ["initial task", "resumed task"]


@pytest.mark.asyncio
async def test_worker_agent_stop_waits_for_background_task_to_finish(agent_config, parent_context, monkeypatch):
    release = asyncio.Event()

    class FakeEngine:
        def __init__(self, config):
            self.config = config

        def set_system_prompt(self, prompt):
            self.prompt = prompt

        def set_tools(self, tools):
            self.tools = tools

        def set_tool_use_context(self, context):
            self.context = context

        def set_can_use_tool(self, can_use_tool):
            self.can_use_tool = can_use_tool

        async def submit_message(self, prompt):
            yield {"type": "content", "content": f"done:{prompt}"}

        def stop(self):
            release.set()

    monkeypatch.setattr("claude_core.agents.worker.QueryEngine", FakeEngine)

    agent = WorkerAgent(config=agent_config, parent_context=parent_context)
    await agent.start_background("initial task")
    await asyncio.sleep(0.1)

    await agent.stop()

    assert agent.status == AgentStatus.STOPPED
    assert agent._background_task is not None
    assert agent._background_task.done() is True


@pytest.mark.asyncio
async def test_worker_agent_get_background_status(agent_config, parent_context):
    """Test get_background_status returns correct status info."""
    agent = WorkerAgent(config=agent_config, parent_context=parent_context)

    # Initially not started
    status = agent.get_background_status()
    assert status["agent_id"] == agent.agent_id
    assert status["status"] == "idle"
    assert status["is_running"] is False
    assert status["is_done"] is True
    assert status["final_response"] == ""  # Empty string when not started
    assert status["message_count"] == 0

    # Start background task
    await agent.start_background("Test task")

    status = agent.get_background_status()
    assert status["agent_id"] == agent.agent_id
    assert status["status"] == "running"
    assert status["is_running"] is True
    assert status["is_done"] is False

    # Clean up
    await agent.stop()


@pytest.mark.asyncio
async def test_worker_agent_resume_background_paused(agent_config, parent_context):
    """Test resume_background resumes a paused agent."""
    agent = WorkerAgent(config=agent_config, parent_context=parent_context)

    await agent.start_background("Test task")
    assert agent.status == AgentStatus.RUNNING

    # Pause the agent
    await agent.pause()
    assert agent.status == AgentStatus.PAUSED

    # Resume should transition back to running
    await agent.resume_background()
    assert agent.status == AgentStatus.RUNNING
    assert parent_context.abort_controller.signal.aborted is False

    # Clean up
    await agent.stop()


@pytest.mark.asyncio
async def test_worker_agent_resume_background_stopped_raises(agent_config, parent_context):
    """Test resume_background raises error for stopped agent."""
    agent = WorkerAgent(config=agent_config, parent_context=parent_context)

    await agent.start_background("Test task")
    await agent.stop()
    assert agent.status == AgentStatus.STOPPED

    # Resume should raise RuntimeError
    with pytest.raises(RuntimeError, match="Cannot resume stopped agent"):
        await agent.resume_background()


@pytest.mark.asyncio
async def test_worker_agent_resume_background_completed_raises(agent_config, parent_context):
    """Test resume_background raises error for completed agent."""
    agent = WorkerAgent(config=agent_config, parent_context=parent_context)

    # Manually set to completed
    agent.status = AgentStatus.COMPLETED

    # Resume should raise RuntimeError
    with pytest.raises(RuntimeError, match="Cannot resume completed agent"):
        await agent.resume_background()


@pytest.mark.asyncio
async def test_worker_agent_resume_background_idle_raises(agent_config, parent_context):
    """Test resume_background raises error for idle (not started) agent."""
    agent = WorkerAgent(config=agent_config, parent_context=parent_context)

    # Resume should raise RuntimeError since not started
    with pytest.raises(RuntimeError, match="has not been started"):
        await agent.resume_background()


@pytest.mark.asyncio
async def test_worker_agent_run_sets_completed_status(agent_config, parent_context, monkeypatch):
    class FakeEngine:
        def __init__(self, config):
            self.config = config

        def set_system_prompt(self, prompt):
            self.prompt = prompt

        def set_tools(self, tools):
            self.tools = tools

        def set_tool_use_context(self, context):
            self.context = context

        async def submit_message(self, prompt):
            yield {"type": "content", "content": "completed"}

        def stop(self):
            return None

    monkeypatch.setattr("claude_core.agents.worker.QueryEngine", FakeEngine)

    agent = WorkerAgent(config=agent_config, parent_context=parent_context)
    result = await agent.run("finish work")

    assert result.status == AgentStatus.COMPLETED
    assert agent.status == AgentStatus.COMPLETED


@pytest.mark.asyncio
async def test_worker_agent_run_unregisters_completed_agent(agent_config, parent_context, monkeypatch):
    runtime = AgentRuntime.get_instance()
    runtime.clear()

    class FakeEngine:
        def __init__(self, config):
            self.config = config

        def set_system_prompt(self, prompt):
            self.prompt = prompt

        def set_tools(self, tools):
            self.tools = tools

        def set_tool_use_context(self, context):
            self.context = context

        async def submit_message(self, prompt):
            yield {"type": "content", "content": "done"}

        def stop(self):
            return None

    monkeypatch.setattr("claude_core.agents.worker.QueryEngine", FakeEngine)

    agent = WorkerAgent(config=agent_config, parent_context=parent_context)
    await agent.run("finish work")

    assert runtime.get_agent(agent.agent_id) is None


@pytest.mark.asyncio
async def test_worker_agent_stop_cleans_runtime_and_tracker_state(agent_config, parent_context, monkeypatch):
    runtime = AgentRuntime.get_instance()
    runtime.clear()
    tracker = BackgroundTaskTracker.get_instance()
    tracker.clear()

    class FakeEngine:
        def __init__(self, config):
            self.config = config

        def set_system_prompt(self, prompt):
            self.prompt = prompt

        def set_tools(self, tools):
            self.tools = tools

        def set_tool_use_context(self, context):
            self.context = context

        def set_can_use_tool(self, can_use_tool):
            self.can_use_tool = can_use_tool

        async def submit_message(self, prompt):
            yield {"type": "content", "content": f"done:{prompt}"}

        def stop(self):
            return None

    monkeypatch.setattr("claude_core.agents.worker.QueryEngine", FakeEngine)

    agent = WorkerAgent(config=agent_config, parent_context=parent_context)
    state = create_task_state(
        task_type=TaskType.BACKGROUND_AGENT,
        subject="Long task",
        description="worker cleanup",
        agent_id=agent.agent_id,
        agent_name="worker",
        model="gpt-4o",
        is_backgrounded=True,
    )
    state.status = TaskStatus.RUNNING.value
    state.started_at = time.time()
    tracker.add_state(state)

    await agent.start_background("initial task")
    await agent.stop()

    assert runtime.get_agent(agent.agent_id) is None
    assert tracker.get_task(agent.agent_id) is None
    assert state.status == AgentStatus.STOPPED.value
    assert state.completed_at is not None


@pytest.mark.asyncio
async def test_worker_agent_parent_abort_stops_background_and_cleans_runtime(
    agent_config,
    parent_context,
    monkeypatch,
):
    runtime = AgentRuntime.get_instance()
    runtime.clear()

    class FakeEngine:
        def __init__(self, config):
            self.config = config

        def set_system_prompt(self, prompt):
            self.prompt = prompt

        def set_tools(self, tools):
            self.tools = tools

        def set_tool_use_context(self, context):
            self.context = context

        def set_can_use_tool(self, can_use_tool):
            self.can_use_tool = can_use_tool

        async def submit_message(self, prompt):
            yield {"type": "content", "content": f"done:{prompt}"}

        def stop(self):
            return None

    monkeypatch.setattr("claude_core.agents.worker.QueryEngine", FakeEngine)

    agent = WorkerAgent(config=agent_config, parent_context=parent_context)
    await agent.start_background("initial task")

    parent_context.abort_controller.abort("user_stop")
    await asyncio.wait_for(agent._background_task, timeout=1.0)

    assert agent.status == AgentStatus.STOPPED
    assert runtime.get_agent(agent.agent_id) is None


@pytest.mark.asyncio
async def test_worker_agent_session_sharing_enabled_by_default(agent_config, parent_context):
    """Test that session sharing is enabled by default."""
    agent = WorkerAgent(config=agent_config, parent_context=parent_context)
    assert agent.get_session_sharing_status() is True


@pytest.mark.asyncio
async def test_worker_agent_disable_session_sharing(agent_config, parent_context):
    """Test disabling session sharing."""
    agent = WorkerAgent(config=agent_config, parent_context=parent_context)
    assert agent.get_session_sharing_status() is True

    agent.disable_session_sharing()
    assert agent.get_session_sharing_status() is False


@pytest.mark.asyncio
async def test_worker_agent_enable_session_sharing(agent_config, parent_context):
    """Test enabling session sharing."""
    agent = WorkerAgent(config=agent_config, parent_context=parent_context)
    agent.disable_session_sharing()
    assert agent.get_session_sharing_status() is False

    agent.enable_session_sharing()
    assert agent.get_session_sharing_status() is True


@pytest.mark.asyncio
async def test_worker_agent_inherits_parent_messages(agent_config, parent_context):
    """Test that child agent inherits messages from parent context when session sharing enabled."""
    from claude_core.models.message import create_user_message

    # Add messages to parent context
    parent_msg1 = create_user_message(content="Hello from parent")
    parent_msg2 = create_user_message(content="Parent continuing conversation")
    parent_context.messages = [parent_msg1, parent_msg2]

    agent = WorkerAgent(config=agent_config, parent_context=parent_context)

    # Child context should have inherited parent's messages
    assert len(agent.context.messages) == 2
    # UserMessage.message = {"role": "user", "content": [{"type": "text", "text": "..."}]}
    msg1_content = agent.context.messages[0].message["content"][0]["text"]
    msg2_content = agent.context.messages[1].message["content"][0]["text"]
    assert msg1_content == "Hello from parent"
    assert msg2_content == "Parent continuing conversation"


@pytest.mark.asyncio
async def test_worker_agent_no_inherit_when_session_sharing_disabled(agent_config, parent_context):
    """Test that child agent does not inherit messages when session sharing disabled."""
    from claude_core.models.message import create_user_message

    # Add messages to parent context
    parent_msg = create_user_message(content="Hello from parent")
    parent_context.messages = [parent_msg]

    agent = WorkerAgent(config=agent_config, parent_context=parent_context)
    agent.disable_session_sharing()

    # Re-create context with session sharing disabled
    agent.context = agent._create_subagent_context()

    # Child context should NOT have parent's messages
    assert len(agent.context.messages) == 0


@pytest.mark.asyncio
async def test_worker_agent_fork_context_increments_depth(agent_config, parent_context):
    """Test that fork context depth is incremented for nested agents."""
    parent_tracking = QueryChainTracking(chain_id="test-chain", depth=0)
    parent_context.query_tracking = parent_tracking

    agent1 = WorkerAgent(config=agent_config, parent_context=parent_context)
    assert agent1.context.query_tracking.depth == 1

    # Create a child of child
    agent2 = WorkerAgent(
        config=agent_config,
        parent_context=agent1.context,
        fork_context=ForkContext(chain_id="test-chain", depth=1),
    )
    assert agent2.context.query_tracking.depth == 2


@pytest.mark.asyncio
async def test_worker_agent_fork_context_shared_chain_id(agent_config, parent_context):
    """Test that forked agents share the same chain_id."""
    parent_tracking = QueryChainTracking(chain_id="shared-chain", depth=0)
    parent_context.query_tracking = parent_tracking

    agent1 = WorkerAgent(config=agent_config, parent_context=parent_context)
    assert agent1.context.query_tracking.chain_id == "shared-chain"

    agent2 = WorkerAgent(
        config=agent_config,
        parent_context=agent1.context,
        fork_context=ForkContext(chain_id="shared-chain", depth=1),
    )
    assert agent2.context.query_tracking.chain_id == "shared-chain"
