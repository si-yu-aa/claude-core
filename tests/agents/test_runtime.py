import pytest

from claude_core.agents.runtime import AgentRuntime


class DummyAgent:
    def __init__(self, agent_id: str):
        self._agent_id = agent_id

    @property
    def agent_id(self) -> str:
        return self._agent_id


def test_agent_runtime_register_and_get_agent():
    runtime = AgentRuntime()
    agent = DummyAgent("agent-runtime")

    runtime.register(agent)

    assert runtime.get_agent("agent-runtime") is agent
    assert "agent-runtime" in runtime.list_agent_ids()


def test_agent_runtime_unregister_agent():
    runtime = AgentRuntime()
    agent = DummyAgent("agent-runtime")
    runtime.register(agent)

    runtime.unregister("agent-runtime")

    assert runtime.get_agent("agent-runtime") is None


def test_agent_runtime_shared_mailbox():
    runtime = AgentRuntime()
    runtime.mailbox.send("agent-a", "agent-b", "hello")

    msg = runtime.mailbox.receive("agent-b")
    assert msg is not None
    assert msg.content == "hello"
