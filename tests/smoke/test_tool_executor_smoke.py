"""Smoke tests for ToolExecutor and tool system.

These tests verify the basic functionality of the tool system.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from claude_core.tools.base import (
    Tool,
    ToolImpl,
    ToolResult,
    ValidationResult,
    PermissionResult,
    build_tool,
    tool_matches_name,
)
from claude_core.tools.streaming_executor import StreamingToolExecutor


class TestToolResult:
    """Smoke tests for ToolResult."""

    def test_tool_result_creation(self):
        """Should create ToolResult with required fields."""
        result = ToolResult(
            tool_use_id="test-123",
            content="Hello, world!",
        )
        assert result.tool_use_id == "test-123"
        assert result.content == "Hello, world!"
        assert result.is_error is False

    def test_tool_result_with_error(self):
        """Should create error ToolResult."""
        result = ToolResult(
            tool_use_id="test-123",
            content="Error occurred",
            is_error=True,
        )
        assert result.is_error is True


class TestValidationResult:
    """Smoke tests for ValidationResult."""

    def test_validation_success(self):
        """Should create success ValidationResult."""
        result = ValidationResult(result=True)
        assert result.result is True

    def test_validation_failure(self):
        """Should create failure ValidationResult."""
        result = ValidationResult(result=False, message="Invalid input", error_code=400)
        assert result.result is False
        assert result.message == "Invalid input"
        assert result.error_code == 400


class TestPermissionResult:
    """Smoke tests for PermissionResult."""

    def test_permission_allow(self):
        """Should create allow PermissionResult."""
        result = PermissionResult(behavior="allow")
        assert result.behavior == "allow"

    def test_permission_deny(self):
        """Should create deny PermissionResult."""
        result = PermissionResult(behavior="deny")
        assert result.behavior == "deny"

    def test_permission_ask(self):
        """Should create ask PermissionResult."""
        result = PermissionResult(behavior="ask")
        assert result.behavior == "ask"


class TestToolImpl:
    """Smoke tests for ToolImpl."""

    def test_tool_impl_basic(self):
        """Should create ToolImpl with basic attributes."""
        tool = ToolImpl(
            name="Read",
            description="Read a file",
            input_schema={"type": "object"},
        )
        assert tool.name == "Read"
        assert tool.description == "Read a file"

    def test_tool_impl_default_methods(self):
        """Should have correct default method values."""
        tool = ToolImpl(name="Test", description="Test", input_schema={})

        assert tool.is_enabled() is True
        assert tool.is_concurrency_safe({}) is False
        assert tool.is_read_only({}) is False
        assert tool.is_destructive({}) is False
        assert tool.interrupt_behavior() == "block"

    def test_tool_impl_with_callable_overrides(self):
        """Should support callable method overrides."""
        tool = ToolImpl(
            name="Read",
            description="Read a file",
            input_schema={},
            is_enabled=lambda: False,
            is_read_only=lambda args: True,
        )

        assert tool.is_enabled() is False
        assert tool.is_read_only({}) is True


class TestBuildTool:
    """Smoke tests for build_tool factory."""

    def test_build_minimal_tool(self):
        """Should build a minimal tool."""
        tool = build_tool({
            "name": "Test",
            "description": "A test tool",
            "input_schema": {"type": "object"},
        })

        assert tool.name == "Test"
        assert tool.is_enabled() is True

    def test_build_tool_with_overrides(self):
        """Should build tool with method overrides."""
        tool = build_tool({
            "name": "Test",
            "description": "A test tool",
            "input_schema": {"type": "object"},
            "is_enabled": lambda: False,
            "is_read_only": lambda args: True,
        })

        assert tool.is_enabled() is False
        assert tool.is_read_only({}) is True


class TestToolMatchesName:
    """Smoke tests for tool_matches_name function."""

    def test_exact_match(self):
        """Should match exact name."""
        tool = build_tool({
            "name": "Read",
            "description": "Read files",
            "input_schema": {},
        })

        assert tool_matches_name(tool, "Read") is True

    def test_no_match(self):
        """Should not match different name."""
        tool = build_tool({
            "name": "Read",
            "description": "Read files",
            "input_schema": {},
        })

        assert tool_matches_name(tool, "Write") is False


class TestStreamingToolExecutorSmoke:
    """Smoke tests for StreamingToolExecutor."""

    def test_executor_initialization(self):
        """Should initialize executor with tools."""
        mock_tool = MagicMock()
        mock_tool.name = "TestTool"

        mock_context = MagicMock()

        executor = StreamingToolExecutor(
            tool_definitions=[mock_tool],
            can_use_tool=lambda x: True,
            tool_use_context=mock_context,
        )

        assert len(executor._tool_definitions) == 1
