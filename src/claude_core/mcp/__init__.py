"""Minimal MCP support for resource discovery and reading."""

from claude_core.mcp.client import MCPClient
from claude_core.mcp.types import MCPResource, MCPResourceContent

__all__ = ["MCPClient", "MCPResource", "MCPResourceContent"]
