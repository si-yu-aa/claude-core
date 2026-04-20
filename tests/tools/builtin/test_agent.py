import pytest

from claude_core.tools.builtin import __all__ as builtin_all
from claude_core.tools.builtin import create_task_tools
from claude_core.tools.builtin.agent import create_agent_tool
from claude_core.models.tool import ToolUseContext, ToolUseContextOptions
from claude_core.utils.abort import AbortController


def test_agent_tool_is_exported_from_builtin_surface():
    assert "create_agent_tool" in builtin_all


@pytest.mark.asyncio
async def test_agent_tool_returns_background_task_id(monkeypatch):
    context = ToolUseContext(
        options=ToolUseContextOptions(tools=[]),
        abort_controller=AbortController(),
    )

    class FakeAgent:
        agent_id = "agent-test"
        _background_task = None

        def __init__(self, config, parent_context):
            self.agent_id = "agent-test"

        async def run(self, prompt):
            return None

        async def start_background(self, prompt):
            return self.agent_id

    monkeypatch.setattr("claude_core.tools.builtin.agent.WorkerAgent", FakeAgent)
    tool = create_agent_tool()
    result = await tool.call(
        {
            "tool_use_id": "agent-call",
            "prompt": "do work",
            "run_in_background": True,
        },
        context,
        lambda *args: True,
    )

    assert result.is_error is False
    assert "task_id:" in result.content.lower()


@pytest.mark.asyncio
async def test_agent_tool_background_uses_worker_start_background(monkeypatch):
    context = ToolUseContext(
        options=ToolUseContextOptions(tools=[]),
        abort_controller=AbortController(),
    )
    called = {}

    class FakeAgent:
        agent_id = "agent-start-bg"
        _background_task = None

        def __init__(self, config, parent_context):
            self.agent_id = "agent-start-bg"

        async def start_background(self, prompt):
            called["prompt"] = prompt
            return self.agent_id

    monkeypatch.setattr("claude_core.tools.builtin.agent.WorkerAgent", FakeAgent)
    tool = create_agent_tool()
    result = await tool.call(
        {
            "tool_use_id": "agent-call",
            "prompt": "continue in background",
            "run_in_background": True,
        },
        context,
        lambda *args: True,
    )

    assert result.is_error is False
    assert called["prompt"] == "continue in background"
