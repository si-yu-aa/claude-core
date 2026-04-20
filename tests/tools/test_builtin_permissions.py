import pytest

from claude_core.models.tool import (
    ToolPermissionContext,
    ToolUseContext,
    ToolUseContextOptions,
)
from claude_core.tools.builtin.bash import create_bash_tool
from claude_core.tools.builtin.file_edit import create_file_edit_tool
from claude_core.tools.builtin.file_read import create_file_read_tool
from claude_core.tools.builtin.file_write import create_file_write_tool
from claude_core.tools.builtin.glob import create_glob_tool
from claude_core.tools.builtin.grep import create_grep_tool
from claude_core.tools.builtin.mcp import create_list_mcp_resources_tool
from claude_core.utils.abort import AbortController


def make_context(
    deny_rules: list[str] | None = None,
    always_allow_rules: list[str] | None = None,
) -> ToolUseContext:
    return ToolUseContext(
        options=ToolUseContextOptions(
            tools=[],
            permission_context=ToolPermissionContext(
                deny_rules=deny_rules or [],
                always_allow_rules=always_allow_rules or [],
            ),
        ),
        abort_controller=AbortController(),
    )


@pytest.mark.asyncio
async def test_file_read_permission_denied():
    tool = create_file_read_tool()
    result = await tool.check_permissions({}, make_context(["file:read"]))
    assert result.behavior == "deny"


@pytest.mark.asyncio
async def test_file_write_permission_denied():
    tool = create_file_write_tool()
    result = await tool.check_permissions({}, make_context(["file:write"]))
    assert result.behavior == "deny"


@pytest.mark.asyncio
async def test_file_edit_permission_denied():
    tool = create_file_edit_tool()
    result = await tool.check_permissions({}, make_context(["file:edit"]))
    assert result.behavior == "deny"


@pytest.mark.asyncio
async def test_glob_permission_denied():
    tool = create_glob_tool()
    result = await tool.check_permissions({}, make_context(["file:glob"]))
    assert result.behavior == "deny"


@pytest.mark.asyncio
async def test_grep_permission_denied():
    tool = create_grep_tool()
    result = await tool.check_permissions({}, make_context(["file:grep"]))
    assert result.behavior == "deny"


@pytest.mark.asyncio
async def test_bash_exec_permission_denied():
    tool = create_bash_tool()
    result = await tool.check_permissions({"command": "touch /tmp/x"}, make_context(["bash:exec"]))
    assert result.behavior == "deny"


@pytest.mark.asyncio
async def test_bash_read_rule_separate_from_exec():
    tool = create_bash_tool()
    read_denied = await tool.check_permissions({"command": "cat README.md"}, make_context(["bash:read"]))
    exec_allowed = await tool.check_permissions({"command": "touch /tmp/x"}, make_context(["bash:read"]))
    assert read_denied.behavior == "deny"
    assert exec_allowed.behavior == "ask"


@pytest.mark.asyncio
async def test_file_read_requires_explicit_allow_for_scoped_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()
    allowed_file = allowed_dir / "note.txt"

    tool = create_file_read_tool()
    allowed = await tool.check_permissions(
        {"file_path": str(allowed_file)},
        make_context(always_allow_rules=[f"file:read:{allowed_dir.resolve()}/**"]),
    )
    blocked = await tool.check_permissions(
        {"file_path": str(tmp_path / 'other.txt')},
        make_context(always_allow_rules=[f"file:read:{allowed_dir.resolve()}/**"]),
    )

    assert allowed.behavior == "allow"
    assert allowed.updated_input["file_path"] == str(allowed_file.resolve())
    assert blocked.behavior == "ask"


@pytest.mark.asyncio
async def test_file_write_rejects_workspace_escape(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    tool = create_file_write_tool()
    result = await tool.check_permissions(
        {"file_path": "../escape.txt"},
        make_context(always_allow_rules=[f"file:write:{workspace.resolve()}/**"]),
    )

    assert result.behavior == "deny"


@pytest.mark.asyncio
async def test_file_edit_normalizes_relative_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    editable = tmp_path / "editable.txt"
    tool = create_file_edit_tool()

    result = await tool.check_permissions(
        {"file_path": "./editable.txt"},
        make_context(always_allow_rules=[f"file:edit:{tmp_path.resolve()}/**"]),
    )

    assert result.behavior == "allow"
    assert result.updated_input["file_path"] == str(editable.resolve())


@pytest.mark.asyncio
async def test_mcp_read_requires_explicit_allow():
    tool = create_list_mcp_resources_tool()
    result = await tool.check_permissions({}, make_context())
    assert result.behavior == "ask"
