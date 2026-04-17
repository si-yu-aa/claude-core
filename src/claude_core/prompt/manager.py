"""Prompt manager for managing and retrieving prompts."""

from pathlib import Path
from typing import Any, Optional
from claude_core.prompt.builder import build_effective_prompt
from claude_core.prompt.parts import (
    get_coordinator_system_prompt,
    get_claude_mds,
    get_git_status,
    build_git_context_section,
    build_claude_md_section,
)
from claude_core.prompt.templates import DEFAULT_SYSTEM_TEMPLATE

class PromptManager:
    """
    Prompt manager for managing prompt templates and configurations.

    Provides:
    - Template storage and retrieval
    - Prompt versioning
    - Dynamic prompt generation
    - Priority-based prompt building
    - Coordinator mode support
    - Git context integration
    - CLAUDE.md discovery
    """

    def __init__(self):
        self._templates: dict[str, str] = {
            "default": DEFAULT_SYSTEM_TEMPLATE,
        }
        self._active_template: str = "default"

    def get_template(self, name: str) -> Optional[str]:
        """Get a template by name."""
        return self._templates.get(name)

    def set_template(self, name: str, template: str) -> None:
        """Set a template by name."""
        self._templates[name] = template

    def list_templates(self) -> list[str]:
        """List all template names."""
        return list(self._templates.keys())

    def set_active_template(self, name: str) -> bool:
        """Set the active template. Returns False if template doesn't exist."""
        if name in self._templates:
            self._active_template = name
            return True
        return False

    def get_active_template(self) -> str:
        """Get the active template."""
        return self._templates.get(self._active_template, DEFAULT_SYSTEM_TEMPLATE)

    def delete_template(self, name: str) -> bool:
        """Delete a template. Returns False if template doesn't exist or is default."""
        if name == "default" or name not in self._templates:
            return False
        del self._templates[name]
        if self._active_template == name:
            self._active_template = "default"
        return True

    def build_effective_prompt(
        self,
        override: str | None = None,
        coordinator: str | None = None,
        agent: str | None = None,
        custom: str | None = None,
        default: str | None = None,
        append: str | None = None,
    ) -> str:
        """
        Build effective prompt using 6-level priority system.

        Priority order (highest to lowest):
        1. override - Loop mode override
        2. coordinator - Coordinator mode
        3. agent - Agent-specific prompt
        4. custom - Custom user prompt
        5. default - Default system prompt (+ append)
        6. append - Additional content to append

        Args:
            override: Override prompt (loop mode)
            coordinator: Coordinator mode prompt
            agent: Agent-specific prompt
            custom: Custom user prompt
            default: Default system prompt (defaults to active template)
            append: Additional content to append

        Returns:
            The effective prompt string based on priority
        """
        if default is None:
            default = self.get_active_template()
        return build_effective_prompt(
            override=override,
            coordinator=coordinator,
            agent=agent,
            custom=custom,
            default=default,
            append=append,
        )

    def get_coordinator_prompt(self) -> str:
        """Get the coordinator system prompt."""
        return get_coordinator_system_prompt()

    def get_claude_mds(self, project_root: str | Path | None = None) -> list[str]:
        """
        Discover CLAUDE.md files in the project hierarchy.

        Args:
            project_root: Root directory to search from.

        Returns:
            List of CLAUDE.md file contents found in the project.
        """
        return get_claude_mds(project_root)

    def get_git_context(self, project_root: str | Path | None = None) -> dict[str, Any]:
        """
        Get git context for the project.

        Args:
            project_root: Root directory to search from.

        Returns:
            Dictionary with git context (branch, status, recent commits).
        """
        return get_git_status(project_root)

    def build_git_context(
        self,
        project_root: str | Path | None = None,
    ) -> str:
        """
        Build git context section.

        Args:
            project_root: Root directory to search from.

        Returns:
            Formatted git context section string.
        """
        git_status = self.get_git_context(project_root)
        return build_git_context_section(git_status)

    def build_claude_md_context(
        self,
        project_root: str | Path | None = None,
    ) -> str:
        """
        Build CLAUDE.md context section.

        Args:
            project_root: Root directory to search from.

        Returns:
            Formatted CLAUDE.md context section string.
        """
        claude_mds = self.get_claude_mds(project_root)
        return build_claude_md_section(claude_mds)