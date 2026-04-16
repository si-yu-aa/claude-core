"""System Prompt Builder."""

from __future__ import annotations

from typing import Any, Optional
from claude_core.prompt.parts import (
    build_base_section,
    build_tools_section,
    build_agents_section,
    build_context_section,
)
from claude_core.prompt.templates import DEFAULT_SYSTEM_TEMPLATE

class SystemPromptBuilder:
    """
    System Prompt Builder.

    Combines multiple parts:
    1. Base instructions
    2. Tool definitions (JSON Schema)
    3. Tool usage rules
    4. Agent definitions
    5. User context
    6. System context
    """

    def __init__(
        self,
        base_instructions: str,
        tools: list[Any],
        agents: list[Any] | None = None,
    ):
        self.base_instructions = base_instructions
        self.tools = tools
        self.agents = agents or []

    def build(
        self,
        user_context: dict[str, str],
        system_context: dict[str, str],
    ) -> str:
        """
        Build the complete system prompt.

        Args:
            user_context: User-specific context (current file, working directory, etc.)
            system_context: System context (OS, environment, etc.)

        Returns:
            Complete system prompt string
        """
        parts = []

        # Base section
        base = build_base_section(self.base_instructions)
        if base:
            parts.append(base)

        # Tools section
        tools_section = build_tools_section(self.tools)
        if tools_section:
            parts.append(tools_section)

        # Agents section
        agents_section = build_agents_section(self.agents)
        if agents_section:
            parts.append(agents_section)

        # Context section
        context_section = build_context_section(user_context, system_context)
        if context_section:
            parts.append(context_section)

        return "\n\n".join(filter(None, parts))

    def build_with_template(
        self,
        template: str,
        user_context: dict[str, str],
        system_context: dict[str, str],
    ) -> str:
        """Build prompt using a custom template."""
        return template.format(
            instructions=self.base_instructions,
            tools=self._format_tools(),
            agents=self._format_agents(),
            user_context=self._format_context(user_context),
            system_context=self._format_context(system_context),
        )

    def _format_tools(self) -> str:
        """Format tools for template."""
        return build_tools_section(self.tools)

    def _format_agents(self) -> str:
        """Format agents for template."""
        return build_agents_section(self.agents)

    def _format_context(self, context: dict[str, str]) -> str:
        """Format context for template."""
        return build_context_section(context, {})