import pytest
from claude_core.tools.base import (
    Tool,
    ToolResult,
    ValidationResult,
    PermissionResult,
    build_tool,
)

def test_validation_result_success():
    result = ValidationResult(result=True)
    assert result.result is True

def test_validation_result_failure():
    result = ValidationResult(
        result=False,
        message="Invalid file path",
        error_code=400
    )
    assert result.result is False
    assert result.message == "Invalid file path"

def test_permission_result_allow():
    result = PermissionResult(behavior="allow")
    assert result.behavior == "allow"

def test_permission_result_deny():
    result = PermissionResult(behavior="deny")
    assert result.behavior == "deny"

def test_build_tool_defaults():
    """Test that build_tool provides sensible defaults."""
    def mock_call(args, context, can_use_tool, on_progress=None):
        return ToolResult(tool_use_id="123", content="result")

    tool_def = {
        "name": "TestTool",
        "description": "A test tool",
        "input_schema": {"type": "object", "properties": {"input": {"type": "string"}}},
        "call": mock_call,
    }

    tool = build_tool(tool_def)

    assert tool.name == "TestTool"
    assert tool.is_enabled() is True
    assert tool.is_concurrency_safe({}) is False
    assert tool.is_read_only({}) is False