import pytest

from claude_core.mcp import MCPClient, MCPResource, MCPResourceContent
from claude_core.models.tool import (
    ToolPermissionContext,
    ToolUseContext,
    ToolUseContextOptions,
)
from claude_core.tools.builtin.mcp import (
    create_list_mcp_resources_tool,
    create_read_mcp_resource_tool,
)
from claude_core.utils.abort import AbortController


def make_context(
    *,
    clients: list[MCPClient] | None = None,
    deny_rules: list[str] | None = None,
) -> ToolUseContext:
    permission_context = None
    if deny_rules is not None:
        permission_context = ToolPermissionContext(deny_rules=deny_rules)
    return ToolUseContext(
        options=ToolUseContextOptions(
            tools=[],
            mcp_clients=clients or [],
            permission_context=permission_context,
        ),
        abort_controller=AbortController(),
    )


@pytest.mark.asyncio
async def test_mcp_client_list_and_read_resource():
    client = MCPClient("demo")
    client.register_resource(
        MCPResource(
            uri="memory://project",
            name="Project Memory",
            server_name="demo",
            description="Shared context",
            mime_type="text/plain",
        ),
        MCPResourceContent(
            uri="memory://project",
            server_name="demo",
            text="cached project notes",
            mime_type="text/plain",
        ),
    )

    resources = await client.list_resources()
    assert len(resources) == 1
    assert resources[0].uri == "memory://project"

    content = await client.read_resource("memory://project")
    assert content is not None
    assert content.text == "cached project notes"


@pytest.mark.asyncio
async def test_list_mcp_resources_tool_lists_registered_resources():
    client = MCPClient("demo")
    client.register_resource(
        MCPResource(
            uri="memory://project",
            name="Project Memory",
            server_name="demo",
            description="Shared context",
        ),
    )
    context = make_context(clients=[client])
    tool = create_list_mcp_resources_tool()

    result = await tool.call(
        {"tool_use_id": "list-id", "server": "demo"},
        context,
        lambda *args: True,
    )

    assert result.is_error is False
    assert "Project Memory" in result.content
    assert "memory://project" in result.content


@pytest.mark.asyncio
async def test_read_mcp_resource_tool_reads_text_content():
    client = MCPClient("demo")
    client.register_resource(
        MCPResource(
            uri="memory://project",
            name="Project Memory",
            server_name="demo",
        ),
        MCPResourceContent(
            uri="memory://project",
            server_name="demo",
            text="project context",
        ),
    )
    context = make_context(clients=[client])
    tool = create_read_mcp_resource_tool()

    result = await tool.call(
        {"tool_use_id": "read-id", "server": "demo", "uri": "memory://project"},
        context,
        lambda *args: True,
    )

    assert result.is_error is False
    assert result.content == "project context"


@pytest.mark.asyncio
async def test_read_mcp_resource_tool_supports_server_name_alias():
    client = MCPClient("demo")
    client.register_resource(
        MCPResource(
            uri="memory://project",
            name="Project Memory",
            server_name="demo",
        ),
        MCPResourceContent(
            uri="memory://project",
            server_name="demo",
            text="project context",
        ),
    )
    context = make_context(clients=[client])
    tool = create_read_mcp_resource_tool()

    validation = await tool.validate_input(
        {"server_name": "demo", "uri": "memory://project"},
        context,
    )
    assert validation.result is True

    result = await tool.call(
        {"tool_use_id": "read-id", "server_name": "demo", "uri": "memory://project"},
        context,
        lambda *args: True,
    )

    assert result.is_error is False
    assert result.content == "project context"


@pytest.mark.asyncio
async def test_mcp_permission_denied():
    tool = create_read_mcp_resource_tool()
    context = make_context(deny_rules=["mcp:read"])

    result = await tool.check_permissions(
        {"server": "demo", "uri": "memory://project"},
        context,
    )

    assert result.behavior == "deny"


@pytest.mark.asyncio
async def test_mcp_permission_secure_by_default():
    tool = create_read_mcp_resource_tool()
    context = make_context()

    result = await tool.check_permissions(
        {"server": "demo", "uri": "memory://project"},
        context,
    )

    assert result.behavior == "ask"
