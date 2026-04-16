"""Tool progress types and utilities."""

from dataclasses import dataclass
from typing import Optional

@dataclass
class ToolProgressData:
    """Base class for tool progress data."""
    tool_use_id: str

@dataclass
class BashProgress(ToolProgressData):
    """Progress for Bash tool execution."""
    phase: str = "starting"
    output: Optional[str] = None
    exit_code: Optional[int] = None