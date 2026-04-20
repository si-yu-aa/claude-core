"""Agent base types."""

from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass

from claude_core.agents.types import AgentConfig, AgentStatus, AgentResult
from claude_core.agents.runtime import AgentRuntime

class BaseAgent(ABC):
    """
    Base class for all agents.

    Defines the interface that all agent implementations must follow.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.status = AgentStatus.IDLE
        self.mailbox = AgentRuntime.get_instance().mailbox

    @abstractmethod
    async def run(self, task: str) -> AgentResult:
        """Run the agent with a task."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the agent."""
        pass

    @abstractmethod
    async def pause(self) -> None:
        """Pause the agent."""
        pass

    @abstractmethod
    async def resume(self) -> None:
        """Resume a paused agent."""
        pass

    @property
    @abstractmethod
    def agent_id(self) -> str:
        """Get the agent's unique ID."""
        pass
