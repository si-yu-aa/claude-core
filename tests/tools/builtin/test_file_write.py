import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from claude_core.tools.builtin.file_write import create_file_write_tool
from claude_core.tools.base import ToolResult
from claude_core.models.tool import ToolUseContext, ToolUseContextOptions
from claude_core.utils.abort import AbortController

@pytest.fixture
def context():
    return ToolUseContext(
        options=ToolUseContextOptions(tools=[], debug=False, main_loop_model="gpt-4o"),
        abort_controller=AbortController(),
    )

@pytest.mark.asyncio
async def test_file_write_basic(context):
    tool = create_file_write_tool()
    workspace = Path.cwd() / ".pytest_tmp"
    workspace.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, dir=workspace) as f:
        temp_path = f.name
    try:
        result = await tool.call(
            {"file_path": temp_path, "content": "Hello, World!", "tool_use_id": "test-id"},
            context,
            lambda *args: True,
        )
        assert isinstance(result, ToolResult)
        assert result.is_error is False
        with open(temp_path, "r") as f:
            assert f.read() == "Hello, World!"
    finally:
        os.unlink(temp_path)

@pytest.mark.asyncio
async def test_file_write_overwrite(context):
    tool = create_file_write_tool()
    workspace = Path.cwd() / ".pytest_tmp"
    workspace.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, dir=workspace) as f:
        f.write("Original content")
        temp_path = f.name
    try:
        result = await tool.call(
            {"file_path": temp_path, "content": "New content", "tool_use_id": "test-id"},
            context,
            lambda *args: True,
        )
        assert result.is_error is False
        with open(temp_path, "r") as f:
            assert f.read() == "New content"
    finally:
        os.unlink(temp_path)
