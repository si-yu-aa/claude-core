import pytest
from claude_core.tools.registry import ToolRegistry
from claude_core.tools.base import Tool, ToolResult, build_tool

@pytest.fixture
def sample_tool():
    def call(args, context, can_use_tool, on_progress=None):
        return ToolResult(tool_use_id="123", content="result")

    return build_tool({
        "name": "TestTool",
        "description": "A test tool",
        "input_schema": {"type": "object"},
        "call": call,
    })

@pytest.fixture
def registry(sample_tool):
    reg = ToolRegistry()
    reg.register(sample_tool)
    return reg

def test_registry_register(registry, sample_tool):
    assert registry.get("TestTool") is sample_tool
    assert sample_tool in registry.list_all()

def test_registry_get_nonexistent(registry):
    assert registry.get("NonExistent") is None

def test_registry_unregister(registry, sample_tool):
    registry.unregister("TestTool")
    assert registry.get("TestTool") is None

def test_registry_clear(registry):
    registry.clear()
    assert len(registry.list_all()) == 0