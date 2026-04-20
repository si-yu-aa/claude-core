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


@pytest.mark.asyncio
async def test_bash_timeout(context):
    tool = create_bash_tool()
    result = await tool.call(
        {
            "command": "python -c \"import time; time.sleep(2)\"",
            "timeout": 1,
            "tool_use_id": "timeout-id",
        },
        context,
        lambda *args: True,
    )

    assert isinstance(result, ToolResult)
    assert result.is_error is True
    assert "timed out" in result.content.lower()


@pytest.mark.asyncio
async def test_bash_abort(context):
    tool = create_bash_tool()

    async def abort_soon():
        await asyncio.sleep(0.1)
        context.abort_controller.abort("user_stop")

    asyncio.create_task(abort_soon())
    result = await tool.call(
        {
            "command": "python -c \"import time; time.sleep(5)\"",
            "timeout": 10,
            "tool_use_id": "abort-id",
        },
        context,
        lambda *args: True,
    )

    assert isinstance(result, ToolResult)
    assert result.is_error is True
    assert "aborted" in result.content.lower()


def test_bash_read_only_detection_rejects_redirects_and_pipes():
    tool = create_bash_tool()

    assert tool.is_read_only({"command": "cat README.md"}) is True
    assert tool.is_read_only({"command": "cat README.md > out.txt"}) is False
    assert tool.is_read_only({"command": "find . -exec rm {} \\;"}) is False
    assert tool.is_read_only({"command": "echo hello | tee out.txt"}) is False
