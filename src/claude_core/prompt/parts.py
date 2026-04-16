"""Prompt parts/components."""

from typing import Any

def build_base_section(instructions: str) -> str:
    """Build the base instructions section."""
    return f"{instructions.strip()}\n"

def build_tools_section(tools: list[Any]) -> str:
    """Build the tools section with tool definitions."""
    if not tools:
        return ""

    lines = ["\n## Available Tools"]
    lines.append("\nYou have access to the following tools:")
    lines.append("")

    for tool in tools:
        name = tool.get("name", tool.name if hasattr(tool, 'name') else "Unknown")
        desc = tool.get("description", tool.description if hasattr(tool, 'description') else "")
        schema = tool.get("input_schema", tool.input_schema if hasattr(tool, 'input_schema') else {})

        lines.append(f"\n### {name}")
        lines.append(f"{desc}")
        if isinstance(schema, dict) and "properties" in schema:
            lines.append("Arguments:")
            for prop_name, prop_info in schema["properties"].items():
                prop_type = prop_info.get("type", "any")
                desc = prop_info.get("description", "")
                lines.append(f"  - {prop_name} ({prop_type}): {desc}")

    return "\n".join(lines)

def build_agents_section(agents: list[Any]) -> str:
    """Build the agents section."""
    if not agents:
        return ""

    lines = ["\n## Available Agents"]
    lines.append("\nYou can delegate tasks to specialized agents:")
    lines.append("")

    for agent in agents:
        name = agent.get("name", "Unknown")
        desc = agent.get("description", "")
        lines.append(f"- **{name}**: {desc}")

    return "\n".join(lines)

def build_context_section(
    user_context: dict[str, str],
    system_context: dict[str, str],
) -> str:
    """Build the context section."""
    parts = []

    if user_context:
        parts.append("### User Context")
        for key, value in user_context.items():
            parts.append(f"- {key}: {value}")

    if system_context:
        parts.append("\n### System Context")
        for key, value in system_context.items():
            parts.append(f"- {key}: {value}")

    return "\n".join(parts) if parts else ""