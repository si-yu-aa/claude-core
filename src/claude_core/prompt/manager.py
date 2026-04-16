"""Prompt manager for managing and retrieving prompts."""

from typing import Optional
from claude_core.prompt.templates import DEFAULT_SYSTEM_TEMPLATE

class PromptManager:
    """
    Prompt manager for managing prompt templates and configurations.

    Provides:
    - Template storage and retrieval
    - Prompt versioning
    - Dynamic prompt generation
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