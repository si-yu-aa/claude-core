"""Prompt management module."""

from claude_core.prompt.builder import SystemPromptBuilder
from claude_core.prompt.manager import PromptManager
from claude_core.prompt.templates import (
    DEFAULT_SYSTEM_TEMPLATE,
    TOOL_USE_TEMPLATE,
    AGENT_DELEGATION_TEMPLATE,
)
from claude_core.prompt.parts import (
    build_base_section,
    build_tools_section,
    build_agents_section,
    build_context_section,
)

__all__ = [
    "SystemPromptBuilder",
    "PromptManager",
    "DEFAULT_SYSTEM_TEMPLATE",
    "TOOL_USE_TEMPLATE",
    "AGENT_DELEGATION_TEMPLATE",
    "build_base_section",
    "build_tools_section",
    "build_agents_section",
    "build_context_section",
]