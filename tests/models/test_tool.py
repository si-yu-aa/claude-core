import pytest
from claude_core.models.tool import (
    ToolUseContext,
    ToolUseBlock,
    ToolDefinition,
)

def test_tool_use_block_creation():
    block = ToolUseBlock(
        id="tool-use-1",
        name="FileRead",
        input={"file_path": "/tmp/test.txt"}
    )
    assert block.id == "tool-use-1"
    assert block.name == "FileRead"
    assert block.input["file_path"] == "/tmp/test.txt"