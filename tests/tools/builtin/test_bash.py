import pytest
import asyncio
from claude_core.tools.builtin.bash import create_bash_tool
from claude_core.tools.base import ToolResult
from claude_core.models.tool import ToolUseContext, ToolUseContextOptions
from claude_core.utils.abort import AbortController

@pytest.fixture
def context():
    return ToolUseContext(
        options=ToolUseContextOptions(
            tools=[],
            debug=False,
            main_loop_model="gpt-4o",
        ),
        abort_controller=AbortController(),
    )

@pytest.mark.asyncio
async def test_bash_echo(context):
    tool = create_bash_tool()
    result = await tool.call(
        {"command": "echo 'Hello from bash'", "tool_use_id": "test-id"},
        context,
        lambda *args: True,
    )

    assert isinstance(result, ToolResult)
    assert "Hello from bash" in result.content
    assert result.is_error is False
