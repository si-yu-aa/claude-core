"""A minimal in-memory MCP client abstraction."""

from __future__ import annotations

from typing import Optional

from claude_core.mcp.types import MCPResource, MCPResourceContent


class MCPClient:
    """Simple MCP client backed by an in-memory resource registry."""

    def __init__(self, server_name: str):
        self.server_name = server_name
        self._resources: dict[str, MCPResource] = {}
        self._resource_contents: dict[str, MCPResourceContent] = {}

    def register_resource(
        self,
        resource: MCPResource,
        content: MCPResourceContent | None = None,
    ) -> None:
        """Register a resource and optional content payload."""
        self._resources[resource.uri] = resource
        if content is not None:
            self._resource_contents[resource.uri] = content

    async def list_resources(self) -> list[MCPResource]:
        """List all resources exposed by this client."""
        return list(self._resources.values())

    async def read_resource(self, uri: str) -> Optional[MCPResourceContent]:
        """Read one resource by URI."""
        if uri in self._resource_contents:
            return self._resource_contents[uri]
        resource = self._resources.get(uri)
        if resource is None:
            return None
        return MCPResourceContent(
            uri=resource.uri,
            server_name=resource.server_name,
            mime_type=resource.mime_type,
            metadata=resource.metadata,
        )
