import pytest
import asyncio
import tempfile
import os
from claude_core.tools.builtin.glob import create_glob_tool
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
def temp_dir():
    import tempfile
    tmpdir = tempfile.mkdtemp()
    # Create test files
    for name in ["file1.txt", "file2.txt", "readme.md", "data.json"]:
        with open(os.path.join(tmpdir, name), "w") as f:
            f.write(f"content of {name}")
    # Create subdirectory with file
    subdir = os.path.join(tmpdir, "subdir")
    os.makedirs(subdir)
    with open(os.path.join(subdir, "nested.txt"), "w") as f:
        f.write("nested content")
    yield tmpdir
    import shutil
    shutil.rmtree(tmpdir)

@pytest.mark.asyncio
async def test_glob_single_pattern(temp_dir, context):
    tool = create_glob_tool()
    result = await tool.call(
        {"pattern": "*.txt", "base_dir": temp_dir, "tool_use_id": "test-id"},
        context,
        lambda *args: True,
    )
    assert isinstance(result, ToolResult)
    assert result.is_error is False
    assert "file1.txt" in result.content
    assert "file2.txt" in result.content

@pytest.mark.asyncio
async def test_glob_recursive(temp_dir, context):
    tool = create_glob_tool()
    result = await tool.call(
        {"pattern": "**/*.txt", "base_dir": temp_dir, "tool_use_id": "test-id"},
        context,
        lambda *args: True,
    )
    assert isinstance(result, ToolResult)
    assert "nested.txt" in result.content or "subdir" in result.content