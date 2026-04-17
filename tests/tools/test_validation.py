import pytest
from unittest.mock import AsyncMock, MagicMock
from claude_core.tools.base import (
    Tool,
    ToolImpl,
    ValidationResult,
    build_tool,
)
from claude_core.models.tool import ToolUseContext, ToolUseContextOptions, ToolPermissionContext


@pytest.fixture
def mock_context():
    """Create a mock tool use context."""
    return MagicMock(spec=ToolUseContext)


@pytest.fixture
def tool_with_validation():
    """Build a tool with custom validate_input."""
    async def custom_validate(input_data, context):
        if "required_field" not in input_data:
            return ValidationResult(
                result=False,
                message="Missing required_field",
                error_code=400
            )
        return ValidationResult(result=True)

    def call(args, context, can_use_tool, on_progress=None):
        return MagicMock(tool_use_id="123", content="result")

    return build_tool({
        "name": "ValidatedTool",
        "description": "A tool with validation",
        "input_schema": {"type": "object", "required": ["required_field"]},
        "call": call,
        "validate_input": custom_validate,
    })


@pytest.fixture
def tool_without_validation():
    """Build a tool without custom validation (uses default)."""
    def call(args, context, can_use_tool, on_progress=None):
        return MagicMock(tool_use_id="123", content="result")

    return build_tool({
        "name": "SimpleTool",
        "description": "A simple tool",
        "input_schema": {"type": "object"},
        "call": call,
    })


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_validation_result_success(self):
        result = ValidationResult(result=True)
        assert result.result is True
        assert result.message == ""
        assert result.error_code == 0

    def test_validation_result_failure(self):
        result = ValidationResult(
            result=False,
            message="Invalid file path",
            error_code=400
        )
        assert result.result is False
        assert result.message == "Invalid file path"
        assert result.error_code == 400

    def test_validation_result_with_all_fields(self):
        result = ValidationResult(
            result=False,
            message="Schema mismatch",
            error_code=422
        )
        assert result.result is False
        assert result.message == "Schema mismatch"
        assert result.error_code == 422


class TestToolValidation:
    """Tests for Tool.validate_input method."""

    @pytest.mark.asyncio
    async def test_default_validation_passes(self, tool_without_validation, mock_context):
        """Test that default validation always returns True."""
        result = await tool_without_validation.validate_input(
            {"any": "data"},
            mock_context
        )
        assert result.result is True

    @pytest.mark.asyncio
    async def test_custom_validation_passes(self, tool_with_validation, mock_context):
        """Test that custom validation passes with valid input."""
        result = await tool_with_validation.validate_input(
            {"required_field": "value"},
            mock_context
        )
        assert result.result is True

    @pytest.mark.asyncio
    async def test_custom_validation_fails(self, tool_with_validation, mock_context):
        """Test that custom validation fails with invalid input."""
        result = await tool_with_validation.validate_input(
            {"other_field": "value"},
            mock_context
        )
        assert result.result is False
        assert result.message == "Missing required_field"
        assert result.error_code == 400

    @pytest.mark.asyncio
    async def test_validation_with_empty_input(self, tool_with_validation, mock_context):
        """Test validation with empty input."""
        result = await tool_with_validation.validate_input(
            {},
            mock_context
        )
        assert result.result is False


class TestBuildToolWithValidation:
    """Tests for build_tool with validation hooks."""

    def test_build_tool_with_validate_input(self):
        """Test that build_tool correctly sets validate_input."""
        custom_validate = AsyncMock(return_value=ValidationResult(result=True))

        tool = build_tool({
            "name": "TestTool",
            "description": "Test",
            "input_schema": {"type": "object"},
            "validate_input": custom_validate,
        })

        assert hasattr(tool, "validate_input")
        assert tool.validate_input is custom_validate

    def test_build_tool_without_validate_input(self):
        """Test that build_tool sets default validate_input when not provided."""
        tool = build_tool({
            "name": "TestTool",
            "description": "Test",
            "input_schema": {"type": "object"},
        })

        assert hasattr(tool, "validate_input")

    def test_validate_input_replaces_default(self):
        """Test that custom validate_input replaces the default."""
        tool_without_custom = build_tool({
            "name": "TestTool",
            "description": "Test",
            "input_schema": {"type": "object"},
        })
        original_validate = tool_without_custom.validate_input

        async def custom_validate(input_data, context):
            return ValidationResult(result=False, message="blocked")
        tool = build_tool({
            "name": "TestTool",
            "description": "Test",
            "input_schema": {"type": "object"},
            "validate_input": custom_validate,
        })

        assert tool.validate_input is not original_validate
        assert tool.validate_input is custom_validate
