import pytest
import asyncio
import tempfile
import os
from claude_core.tools.builtin.grep import create_grep_tool
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
def temp_files():
    tmpdir = tempfile.mkdtemp()
    files = {
        "file1.txt": "Hello world\nThis is a test\nGoodbye",
        "file2.txt": "Hello again\nAnother test file\nWith hello in it",
    }
    for name, content in files.items():
        with open(os.path.join(tmpdir, name), "w") as f:
            f.write(content)
    yield tmpdir
    import shutil
    shutil.rmtree(tmpdir)

@pytest.mark.asyncio
async def test_grep_basic(temp_files, context):
    tool = create_grep_tool()
    result = await tool.call(
        {"pattern": "hello", "base_dir": temp_files, "tool_use_id": "test-id"},
        context,
        lambda *args: True,
    )
    assert isinstance(result, ToolResult)
    assert result.is_error is False
    assert "file1.txt" in result.content
    assert "file2.txt" in result.content

@pytest.mark.asyncio
async def test_grep_case_insensitive(temp_files, context):
    tool = create_grep_tool()
    result = await tool.call(
        {"pattern": "HELLO", "base_dir": temp_files, "case_sensitive": False, "tool_use_id": "test-id"},
        context,
        lambda *args: True,
    )
    assert isinstance(result, ToolResult)
    assert result.is_error is False
    assert "file1.txt" in result.content