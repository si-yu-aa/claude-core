import pytest
from claude_core.agents.worker import WorkerAgent
from claude_core.agents.types import AgentConfig, AgentStatus, AgentResult, ForkContext
from claude_core.utils.abort import AbortController

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
