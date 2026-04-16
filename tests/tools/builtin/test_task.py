import pytest
import asyncio
from claude_core.tools.builtin.task import create_task_tools
from claude_core.tools.base import Tool
from claude_core.models.tool import ToolUseContext, ToolUseContextOptions
from claude_core.utils.abort import AbortController

@pytest.fixture
def context():
    return ToolUseContext(
        options=ToolUseContextOptions(tools=[], debug=False, main_loop_model="gpt-4o"),
        abort_controller=AbortController(),
    )

def test_task_tools_created():
    tools = create_task_tools()
    assert isinstance(tools, list)
    assert len(tools) == 4
    tool_names = [t.name for t in tools]
    assert "TaskCreate" in tool_names
    assert "TaskUpdate" in tool_names
    assert "TaskList" in tool_names
    assert "TaskGet" in tool_names

@pytest.mark.asyncio
async def test_task_create_basic(context):
    tools = create_task_tools()
    task_create = next(t for t in tools if t.name == "TaskCreate")
    result = await task_create.call(
        {"title": "Test task", "description": "A test task", "tool_use_id": "test-id"},
        context,
        lambda *args: True,
    )
    assert result.is_error is False
    assert "Test task" in result.content

@pytest.mark.asyncio
async def test_task_list_basic(context):
    tools = create_task_tools()
    task_list = next(t for t in tools if t.name == "TaskList")
    result = await task_list.call(
        {"tool_use_id": "test-id"},
        context,
        lambda *args: True,
    )
    assert result.is_error is False