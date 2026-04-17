"""Agent-related type definitions."""

from dataclasses import dataclass, field
from typing import Optional, Any, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from claude_core.models.message import Message

class AgentStatus(Enum):
    """Agent lifecycle status."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ERROR = "error"

@dataclass
class ForkContext:
    """Context for forked subagents."""
    chain_id: str
    depth: int

@dataclass
class AgentConfig:
    """Configuration for an agent."""
    name: str
    description: str
    system_prompt: str
    tools: list[Any] = field(default_factory=list)
    model: Optional[str] = None
    max_turns: Optional[int] = None

@dataclass
class AgentResult:
    """Result from an agent execution."""
    agent_id: str
    messages: list["Message"]
    final_response: str
    status: AgentStatus = AgentStatus.COMPLETED