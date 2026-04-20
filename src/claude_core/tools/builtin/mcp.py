"""Built-in MCP resource tools."""

from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from claude_core.tools.base import Tool, ToolResult, ValidationResult, build_tool
from claude_core.tools.permissions import build_permission_checker

if TYPE_CHECKING:
    from claude_core.models.tool import ToolUseContext
    from claude_core.mcp.types import MCPResource, MCPResourceContent


async def _get_all_resources(context: "ToolUseContext") -> list["MCPResource"]:
    cached = getattr(context.options, "mcp_resources", {}) or {}
    resources = []
    for server_resources in cached.values():
        resources.extend(server_resources)

    for client in getattr(context.options, "mcp_clients", []) or []:
        client_resources = await client.list_resources()
        resources.extend(client_resources)
        cached[client.server_name] = client_resources

    context.options.mcp_resources = cached
    deduped: dict[tuple[str, str], MCPResource] = {}
    for resource in resources:
        deduped[(resource.server_name, resource.uri)] = resource
    return list(deduped.values())


def _resolve_server_name(args: dict) -> str | None:
    """Resolve the canonical MCP server argument."""
    return args.get("server") or args.get("server_name")


def create_list_mcp_resources_tool() -> Tool:
    async def call(
        args: dict,
        context: "ToolUseContext",
        can_use_tool: Callable,
        on_progress: Callable | None = None,
    ) -> ToolResult:
        server_name = _resolve_server_name(args)
        resources = await _get_all_resources(context)
        if server_name:
            resources = [r for r in resources if r.server_name == server_name]

        if not resources:
            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content="No MCP resources found",
                is_error=False,
            )

        lines = [f"MCP resources ({len(resources)}):"]
        for resource in resources:
            line = f"- [{resource.server_name}] {resource.name} ({resource.uri})"
            if resource.description:
                line += f": {resource.description}"
            lines.append(line)
        return ToolResult(
            tool_use_id=args.get("tool_use_id", ""),
            content="\n".join(lines),
            is_error=False,
        )

    return build_tool({
        "name": "ListMcpResources",
        "description": "List available MCP resources from connected MCP servers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "server": {
                    "type": "string",
                    "description": "Optional MCP server name filter",
                },
                "server_name": {
                    "type": "string",
                    "description": "Deprecated alias for server",
                },
            },
        },
        "call": call,
        "is_read_only": lambda args: True,
        "is_concurrency_safe": lambda args: True,
        "check_permissions": build_permission_checker(
            lambda args: "mcp:read",
            "mcp_list_resources",
        ),
    })


def create_read_mcp_resource_tool() -> Tool:
    async def validate_input(input_data: dict, context: "ToolUseContext") -> ValidationResult:
        if not _resolve_server_name(input_data):
            return ValidationResult(
                result=False,
                message="server or server_name is required",
                error_code=400,
            )
        if not input_data.get("uri"):
            return ValidationResult(result=False, message="uri is required", error_code=400)
        return ValidationResult(result=True)

    async def call(
        args: dict,
        context: "ToolUseContext",
        can_use_tool: Callable,
        on_progress: Callable | None = None,
    ) -> ToolResult:
        server_name = _resolve_server_name(args)
        uri = args.get("uri")

        client = next(
            (c for c in getattr(context.options, "mcp_clients", []) or [] if c.server_name == server_name),
            None,
        )
        content = None
        if client is not None:
            content = await client.read_resource(uri)

        if content is None:
            cached_resources = getattr(context.options, "mcp_resources", {}) or {}
            resource = next(
                (r for r in cached_resources.get(server_name, []) if r.uri == uri),
                None,
            )
            if resource is not None:
                from claude_core.mcp.types import MCPResourceContent

                content = MCPResourceContent(
                    uri=resource.uri,
                    server_name=resource.server_name,
                    mime_type=resource.mime_type,
                    metadata=resource.metadata,
                )

        if content is None:
            return ToolResult(
                tool_use_id=args.get("tool_use_id", ""),
                content=f"MCP resource not found: [{server_name}] {uri}",
                is_error=True,
            )

        payload = content.text
        if payload is None and content.blob is not None:
            payload = f"<binary:{len(content.blob)} bytes>"
        if payload is None:
            payload = "(empty resource)"

        return ToolResult(
            tool_use_id=args.get("tool_use_id", ""),
            content=payload,
            is_error=False,
        )

    return build_tool({
        "name": "ReadMcpResource",
        "description": "Read one MCP resource by server name and URI.",
        "input_schema": {
            "type": "object",
            "properties": {
                "server": {
                    "type": "string",
                    "description": "MCP server name",
                },
                "server_name": {
                    "type": "string",
                    "description": "Deprecated alias for server",
                },
                "uri": {
                    "type": "string",
                    "description": "Resource URI",
                },
            },
            "required": ["uri"],
        },
        "call": call,
        "validate_input": validate_input,
        "is_read_only": lambda args: True,
        "is_concurrency_safe": lambda args: True,
        "check_permissions": build_permission_checker(
            lambda args: "mcp:read",
            "mcp_read_resource",
        ),
    })
