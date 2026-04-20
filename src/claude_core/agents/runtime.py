"""Shared runtime registry for agents and their mailbox."""

from __future__ import annotations

from typing import Any

from claude_core.agents.mailbox import Mailbox


class AgentRuntime:
    """Singleton registry for live agents and shared messaging."""

    _instance: "AgentRuntime | None" = None

    def __init__(self) -> None:
        self._agents: dict[str, Any] = {}
        self.mailbox = Mailbox()

    @classmethod
    def get_instance(cls) -> "AgentRuntime":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, agent: Any) -> None:
        self._agents[agent.agent_id] = agent

    def unregister(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)

    def get_agent(self, agent_id: str) -> Any | None:
        return self._agents.get(agent_id)

    def list_agent_ids(self) -> list[str]:
        return list(self._agents.keys())

    def describe_agent(self, agent_id: str) -> dict[str, Any] | None:
        agent = self.get_agent(agent_id)
        if agent is None:
            return None

        status = getattr(agent, "status", None)
        status_value = getattr(status, "value", str(status)) if status is not None else "unknown"
        messages = getattr(agent, "_messages", []) or []
        final_response = getattr(agent, "_final_response", "") or ""
        pending_inbox = self.mailbox.pending_count(agent_id)
        return {
            "agent_id": agent_id,
            "status": status_value,
            "message_count": len(messages),
            "final_response": final_response,
            "pending_inbox": pending_inbox,
        }

    def list_agents(self) -> list[dict[str, Any]]:
        return [self.describe_agent(agent_id) for agent_id in self.list_agent_ids() if self.describe_agent(agent_id) is not None]

    def clear(self) -> None:
        self._agents.clear()
        self.mailbox.clear()
