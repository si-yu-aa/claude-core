"""Prompt parts/components."""

import subprocess
from pathlib import Path
from typing import Any


COORDINATOR_SYSTEM_PROMPT = """You are a coordinator agent responsible for orchestrating multiple specialized agents to complete complex tasks.

Your responsibilities:
- Break down complex tasks into smaller, manageable subtasks
- Delegate subtasks to appropriate specialized agents
- Collect and synthesize results from agents
- Handle inter-agent communication and dependencies
- Ensure overall task completion and quality

When coordinating:
- Clearly communicate task requirements to agents
- Track progress across all agent tasks
- Handle failures and adapt coordination strategy
- Provide clear final output to the user
"""


def get_coordinator_system_prompt() -> str:
    """Get the coordinator system prompt for coordinator mode."""
    return COORDINATOR_SYSTEM_PROMPT


def get_claude_mds(project_root: str | Path | None = None) -> list[str]:
    """
    Discover CLAUDE.md files in the project hierarchy.

    Args:
        project_root: Root directory to search from. Defaults to current working directory.

    Returns:
        List of CLAUDE.md file contents found in the project.
    """
    if project_root is None:
        project_root = Path.cwd()
    else:
        project_root = Path(project_root)

    claude_mds = []
    for claude_md in project_root.glob("**/CLAUDE.md"):
        try:
            content = claude_md.read_text()
            claude_mds.append(content)
        except (OSError, IOError):
            pass

    return claude_mds


def get_git_status(project_root: str | Path | None = None) -> dict[str, Any]:
    """
    Get git context for the project.

    Args:
        project_root: Root directory to search from. Defaults to current working directory.

    Returns:
        Dictionary with git context (branch, status, recent commits).
    """
    if project_root is None:
        project_root = Path.cwd()
    else:
        project_root = Path(project_root)

    result: dict[str, Any] = {}

    # Get current branch
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if branch.returncode == 0:
            result["branch"] = branch.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        pass

    # Get git status (short format)
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if status.returncode == 0:
            lines = status.stdout.strip().split("\n")
            result["status"] = [line for line in lines if line]
    except (subprocess.SubprocessError, OSError):
        pass

    # Get recent commits (last 5)
    try:
        commits = subprocess.run(
            ["git", "log", "--oneline", "-5"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if commits.returncode == 0:
            result["recent_commits"] = commits.stdout.strip().split("\n")
    except (subprocess.SubprocessError, OSError):
        pass

    return result


def build_git_context_section(git_status: dict[str, Any]) -> str:
    """Build a git context section from git status."""
    if not git_status:
        return ""

    lines = ["\n## Git Context"]
    if "branch" in git_status:
        lines.append(f"**Branch:** {git_status['branch']}")

    if "status" in git_status and git_status["status"]:
        lines.append("\n**Modified files:**")
        for file_status in git_status["status"][:10]:  # Limit to first 10
            lines.append(f"  {file_status}")
        if len(git_status["status"]) > 10:
            lines.append(f"  ... and {len(git_status['status']) - 10} more")

    if "recent_commits" in git_status and git_status["recent_commits"]:
        lines.append("\n**Recent commits:**")
        for commit in git_status["recent_commits"][:5]:
            lines.append(f"  {commit}")

    return "\n".join(lines)


def build_claude_md_section(claude_mds: list[str]) -> str:
    """Build a section from CLAUDE.md contents."""
    if not claude_mds:
        return ""

    lines = ["\n## Project CLAUDE.md Contents"]
    for i, content in enumerate(claude_mds, 1):
        lines.append(f"\n--- CLAUDE.md {i} ---")
        lines.append(content.strip())

    return "\n".join(lines)


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