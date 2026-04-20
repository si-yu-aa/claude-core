import pytest
from unittest.mock import AsyncMock, MagicMock
from claude_core.tools.base import (
    Tool,
    ToolImpl,
    PermissionResult,
    build_tool,
)
from claude_core.models.tool import ToolUseContext, ToolPermissionContext
from claude_core.tools.permissions import (
    build_permission_checker,
    normalize_file_path,
)


class TestToolPermissionContext:
    """Tests for ToolPermissionContext dataclass."""

    def test_default_context(self):
        """Test default ToolPermissionContext with no rules."""
        ctx = ToolPermissionContext()
        assert ctx.deny_rules == []
        assert ctx.always_allow_rules == []
        assert ctx.input_schema == {}

    def test_context_with_rules(self):
        """Test ToolPermissionContext with deny and always_allow rules."""
        ctx = ToolPermissionContext(
            deny_rules=["file:write", "file:delete"],
            always_allow_rules=["file:read"],
            input_schema={"type": "object"}
        )
        assert ctx.deny_rules == ["file:write", "file:delete"]
        assert ctx.always_allow_rules == ["file:read"]

    def test_is_deny_rule(self):
        """Test is_deny_rule method."""
        ctx = ToolPermissionContext(deny_rules=["file:write", "file:delete"])
        assert ctx.is_deny_rule("file:write") is True
        assert ctx.is_deny_rule("file:read") is False

    def test_is_always_allow_rule(self):
        """Test is_always_allow_rule method."""
        ctx = ToolPermissionContext(always_allow_rules=["file:read", "file:glob"])
        assert ctx.is_always_allow_rule("file:read") is True
        assert ctx.is_always_allow_rule("file:write") is False

    def test_should_deny_without_always_allow(self):
        """Test should_deny when rule is denied but not always allowed."""
        ctx = ToolPermissionContext(
            deny_rules=["file:write"],
            always_allow_rules=[]
        )
        assert ctx.should_deny("file:write") is True

    def test_should_deny_with_always_allow(self):
        """Test should_deny when rule is both denied and always allowed."""
        ctx = ToolPermissionContext(
            deny_rules=["file:write"],
            always_allow_rules=["file:write"]
        )
        assert ctx.should_deny("file:write") is False

    def test_should_deny_non_denied_rule(self):
        """Test should_deny when rule is not denied."""
        ctx = ToolPermissionContext(
            deny_rules=["file:write"],
            always_allow_rules=[]
        )
        assert ctx.should_deny("file:read") is False


class TestPermissionResult:
    """Tests for PermissionResult dataclass."""

    def test_permission_result_allow(self):
        result = PermissionResult(behavior="allow")
        assert result.behavior == "allow"
        assert result.updated_input is None
        assert result.message is None
        assert result.decision_classification is None

    def test_permission_result_deny(self):
        result = PermissionResult(behavior="deny", message="blocked")
        assert result.behavior == "deny"
        assert result.message == "blocked"

    def test_permission_result_ask(self):
        result = PermissionResult(behavior="ask")
        assert result.behavior == "ask"

    def test_permission_result_with_updated_input(self):
        result = PermissionResult(
            behavior="allow",
            updated_input={"sanitized": True}
        )
        assert result.behavior == "allow"
        assert result.updated_input == {"sanitized": True}

    def test_permission_result_with_classification(self):
        result = PermissionResult(
            behavior="allow",
            decision_classification="trusted_operation"
        )
        assert result.decision_classification == "trusted_operation"


class TestToolPermissions:
    """Tests for Tool.check_permissions method."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock tool use context."""
        return MagicMock(spec=ToolUseContext)

    @pytest.fixture
    def tool_with_permissions(self):
        """Build a tool with custom check_permissions."""
        async def custom_check(input_data, context):
            if input_data.get("action") == "delete":
                return PermissionResult(
                    behavior="deny",
                    decision_classification="destructive_action"
                )
            return PermissionResult(behavior="allow")

        def call(args, context, can_use_tool, on_progress=None):
            return MagicMock(tool_use_id="123", content="result")

        return build_tool({
            "name": "PermissionedTool",
            "description": "A tool with permissions",
            "input_schema": {"type": "object"},
            "call": call,
            "check_permissions": custom_check,
        })

    @pytest.fixture
    def tool_without_permissions(self):
        """Build a tool without custom permissions (uses default)."""
        def call(args, context, can_use_tool, on_progress=None):
            return MagicMock(tool_use_id="123", content="result")

        return build_tool({
            "name": "SimpleTool",
            "description": "A simple tool",
            "input_schema": {"type": "object"},
            "call": call,
        })

    @pytest.mark.asyncio
    async def test_default_permissions_allow(self, tool_without_permissions, mock_context):
        """Test that tools without custom hooks still default to allow."""
        result = await tool_without_permissions.check_permissions(
            {"any": "data"},
            mock_context
        )
        assert result.behavior == "allow"

    @pytest.mark.asyncio
    async def test_custom_permissions_allow(self, tool_with_permissions, mock_context):
        """Test that custom permissions allow non-restricted actions."""
        result = await tool_with_permissions.check_permissions(
            {"action": "read"},
            mock_context
        )
        assert result.behavior == "allow"

    @pytest.mark.asyncio
    async def test_custom_permissions_deny(self, tool_with_permissions, mock_context):
        """Test that custom permissions deny restricted actions."""
        result = await tool_with_permissions.check_permissions(
            {"action": "delete"},
            mock_context
        )
        assert result.behavior == "deny"
        assert result.decision_classification == "destructive_action"

    @pytest.mark.asyncio
    async def test_check_permissions_with_empty_input(self, tool_with_permissions, mock_context):
        """Test permissions check with empty input."""
        result = await tool_with_permissions.check_permissions(
            {},
            mock_context
        )
        assert result.behavior == "allow"


class TestBuildToolWithPermissions:
    """Tests for build_tool with permission hooks."""

    def test_build_tool_with_check_permissions(self):
        """Test that build_tool correctly sets check_permissions."""
        custom_check = AsyncMock(return_value=PermissionResult(behavior="allow"))

        tool = build_tool({
            "name": "TestTool",
            "description": "Test",
            "input_schema": {"type": "object"},
            "check_permissions": custom_check,
        })

        assert hasattr(tool, "check_permissions")
        assert tool.check_permissions is custom_check

    def test_build_tool_without_check_permissions(self):
        """Test that build_tool sets default check_permissions when not provided."""
        tool = build_tool({
            "name": "TestTool",
            "description": "Test",
            "input_schema": {"type": "object"},
        })

        assert hasattr(tool, "check_permissions")

    def test_check_permissions_replaces_default(self):
        """Test that custom check_permissions replaces the default."""
        from claude_core.tools.base import ToolImpl

        tool = build_tool({
            "name": "TestTool",
            "description": "Test",
            "input_schema": {"type": "object"},
        })

        original_check = tool.check_permissions

        custom_check = lambda input_data, context: PermissionResult(behavior="deny")
        tool2 = build_tool({
            "name": "TestTool",
            "description": "Test",
            "input_schema": {"type": "object"},
            "check_permissions": custom_check,
        })

        assert tool2.check_permissions is not original_check
        assert tool2.check_permissions is custom_check


class TestPermissionHelpers:
    @pytest.fixture
    def secure_context(self):
        ctx = MagicMock(spec=ToolUseContext)
        ctx.options = MagicMock()
        ctx.options.permission_context = ToolPermissionContext(
            always_allow_rules=["file:read:/workspace/docs/**"]
        )
        return ctx

    @pytest.mark.asyncio
    async def test_permission_checker_secure_by_default_without_context(self):
        checker = build_permission_checker(
            lambda args: {"rule": "file:read"},
            "file_read",
        )
        ctx = MagicMock(spec=ToolUseContext)
        ctx.options = MagicMock()
        ctx.options.permission_context = None

        result = await checker({"file_path": "README.md"}, ctx)

        assert result.behavior == "ask"

    @pytest.mark.asyncio
    async def test_permission_checker_requires_explicit_allow(self):
        checker = build_permission_checker(
            lambda args: {"rule": "file:write"},
            "file_write",
        )
        ctx = MagicMock(spec=ToolUseContext)
        ctx.options = MagicMock()
        ctx.options.permission_context = ToolPermissionContext()

        result = await checker({"file_path": "README.md"}, ctx)

        assert result.behavior == "ask"

    @pytest.mark.asyncio
    async def test_permission_checker_supports_path_scoped_rules(self, secure_context):
        checker = build_permission_checker(
            lambda args: {
                "rule": "file:read",
                "path": "/workspace/docs/readme.md",
                "updated_input": {"file_path": "/workspace/docs/readme.md"},
            },
            "file_read",
        )

        result = await checker({"file_path": "docs/readme.md"}, secure_context)

        assert result.behavior == "allow"
        assert result.updated_input == {"file_path": "/workspace/docs/readme.md"}

    @pytest.mark.asyncio
    async def test_permission_checker_denies_matching_path_rule(self):
        checker = build_permission_checker(
            lambda args: {
                "rule": "file:edit",
                "path": "/workspace/secrets.txt",
            },
            "file_edit",
        )
        ctx = MagicMock(spec=ToolUseContext)
        ctx.options = MagicMock()
        ctx.options.permission_context = ToolPermissionContext(
            deny_rules=["file:edit:/workspace/secrets.txt"]
        )

        result = await checker({"file_path": "/workspace/secrets.txt"}, ctx)

        assert result.behavior == "deny"


class TestNormalizeFilePath:
    def test_normalize_file_path_resolves_relative_path_inside_workspace(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        normalized = normalize_file_path("docs/../docs/readme.txt")

        assert normalized == str((docs_dir / "readme.txt").resolve())

    def test_normalize_file_path_rejects_escape_from_workspace(self, tmp_path, monkeypatch):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("x")
        monkeypatch.chdir(workspace)

        with pytest.raises(PermissionError):
            normalize_file_path("../outside.txt")
