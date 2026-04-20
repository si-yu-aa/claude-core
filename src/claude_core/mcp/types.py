"""Types for minimal MCP resource handling."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class MCPResource:
    """Metadata for an MCP resource."""

    uri: str
    name: str
    server_name: str
    description: str | None = None
    mime_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPResourceContent:
    """Resolved MCP resource content."""

    uri: str
    server_name: str
    text: str | None = None
    blob: bytes | None = None
    mime_type: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
