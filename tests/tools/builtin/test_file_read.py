import pytest
import asyncio
from claude_core.tools.builtin.file_read import create_file_read_tool
from claude_core.tools.base import ToolResult
from claude_core.models.tool import ToolUseContext, ToolUseContextOptions
from claude_core.utils.abort import AbortController
import tempfile
import os

@pytest.fixture
def temp_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Hello, World!")
        f.write("\nSecond line")
        temp_path = f.name
    yield temp_path
    os.unlink(temp_path)

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
async def test_file_read_basic(temp_file, context):
    tool = create_file_read_tool()
    result = await tool.call(
        {"file_path": temp_file, "tool_use_id": "test-id"},
        context,
        lambda *args: True,
    )

    assert isinstance(result, ToolResult)
    assert "Hello, World!" in result.content
    assert result.is_error is False

@pytest.mark.asyncio
async def test_file_read_nonexistent(temp_file, context):
    tool = create_file_read_tool()
    result = await tool.call(
        {"file_path": "/nonexistent/file.txt", "tool_use_id": "test-id"},
        context,
        lambda *args: True,
    )

    assert result.is_error is True
    assert "No such file" in str(result.content)
