import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from claude_core.tools.builtin.file_edit import create_file_edit_tool
from claude_core.tools.base import ToolResult
from claude_core.models.tool import ToolUseContext, ToolUseContextOptions
from claude_core.utils.abort import AbortController

@pytest.fixture
def context():
    return ToolUseContext(
        options=ToolUseContextOptions(tools=[], debug=False, main_loop_model="gpt-4o"),
        abort_controller=AbortController(),
    )

@pytest.fixture
def temp_file():
    workspace = Path.cwd() / ".pytest_tmp"
    workspace.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, dir=workspace) as f:
        f.write("Hello, World!\nThis is a test file.\nGoodbye!")
        temp_path = f.name
    yield temp_path
    os.unlink(temp_path)

@pytest.mark.asyncio
async def test_file_edit_replace(temp_file, context):
    tool = create_file_edit_tool()
    result = await tool.call(
        {
            "file_path": temp_file,
            "search": "Hello, World!",
            "replace": "Hi, Everyone!",
            "tool_use_id": "test-id",
        },
        context,
        lambda *args: True,
    )
    assert isinstance(result, ToolResult)
    assert result.is_error is False
    with open(temp_file, "r") as f:
        content = f.read()
        assert "Hi, Everyone!" in content
        assert "Hello, World!" not in content

@pytest.mark.asyncio
async def test_file_edit_file_not_found(context):
    tool = create_file_edit_tool()
    missing_path = Path.cwd() / ".pytest_tmp" / "missing-edit.txt"
    result = await tool.call(
        {
            "file_path": str(missing_path),
            "search": "something",
            "replace": "something else",
            "tool_use_id": "test-id",
        },
        context,
        lambda *args: True,
    )
    assert result.is_error is True
