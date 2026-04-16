import pytest
from claude_core.agents.worker import WorkerAgent
from claude_core.agents.types import AgentConfig, AgentStatus, AgentResult
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

def test_agent_config_creation(agent_config):
    assert agent_config.name == "TestAgent"
    assert agent_config.model == "gpt-4o"
    assert agent_config.max_turns == 10

def test_agent_status_enum():
    from claude_core.agents.types import AgentStatus
    assert AgentStatus.IDLE.value == "idle"
    assert AgentStatus.RUNNING.value == "running"
    assert AgentStatus.STOPPED.value == "stopped"

@pytest.mark.asyncio
async def test_worker_agent_initialization(agent_config, parent_context):
    agent = WorkerAgent(config=agent_config, parent_context=parent_context)
    assert agent.agent_id.startswith("agent_")
    assert agent.status == AgentStatus.IDLE
    assert agent.config == agent_config