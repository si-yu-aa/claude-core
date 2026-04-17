import pytest
from pathlib import Path
from claude_core.prompt.builder import SystemPromptBuilder, build_effective_prompt
from claude_core.prompt.manager import PromptManager
from claude_core.prompt.parts import (
    get_coordinator_system_prompt,
    get_claude_mds,
    get_git_status,
    build_git_context_section,
    build_claude_md_section,
)

@pytest.fixture
def builder():
    return SystemPromptBuilder(
        base_instructions="You are a helpful coding assistant.",
        tools=[],
        agents=[],
    )


@pytest.fixture
def prompt_manager():
    return PromptManager()


def test_builder_initialization(builder):
    assert builder.base_instructions == "You are a helpful coding assistant."


def test_builder_build_empty_context(builder):
    prompt = builder.build(user_context={}, system_context={})
    assert "You are a helpful coding assistant." in prompt


def test_builder_build_with_context(builder):
    builder_with_context = SystemPromptBuilder(
        base_instructions="You are a helpful assistant.",
        tools=[],
        agents=[],
    )
    prompt = builder_with_context.build(
        user_context={"current_file": "main.py"},
        system_context={"os": "Linux"},
    )
    assert "current_file" in prompt
    assert "main.py" in prompt
    assert "os" in prompt
    assert "Linux" in prompt


# Priority system tests

def test_priority_override_highest():
    """Override should have highest priority."""
    result = build_effective_prompt(
        override="Override prompt",
        coordinator="Coordinator prompt",
        agent="Agent prompt",
        custom="Custom prompt",
        default="Default prompt",
        append="Append prompt",
    )
    assert result == "Override prompt"


def test_priority_coordinator_second():
    """Coordinator should have second priority."""
    result = build_effective_prompt(
        override=None,
        coordinator="Coordinator prompt",
        agent="Agent prompt",
        custom="Custom prompt",
        default="Default prompt",
        append="Append prompt",
    )
    assert result == "Coordinator prompt"


def test_priority_agent_third():
    """Agent should have third priority."""
    result = build_effective_prompt(
        override=None,
        coordinator=None,
        agent="Agent prompt",
        custom="Custom prompt",
        default="Default prompt",
        append="Append prompt",
    )
    assert result == "Agent prompt"


def test_priority_custom_fourth():
    """Custom should have fourth priority."""
    result = build_effective_prompt(
        override=None,
        coordinator=None,
        agent=None,
        custom="Custom prompt",
        default="Default prompt",
        append="Append prompt",
    )
    assert result == "Custom prompt"


def test_priority_default_fifth():
    """Default should have fifth priority (append appended when set)."""
    result = build_effective_prompt(
        override=None,
        coordinator=None,
        agent=None,
        custom=None,
        default="Default prompt",
        append="Append prompt",
    )
    assert result == "Default prompt\n\nAppend prompt"


def test_priority_default_only():
    """Default alone without append."""
    result = build_effective_prompt(
        override=None,
        coordinator=None,
        agent=None,
        custom=None,
        default="Default prompt",
        append=None,
    )
    assert result == "Default prompt"


def test_priority_all_none():
    """All none should return empty string."""
    result = build_effective_prompt(
        override=None,
        coordinator=None,
        agent=None,
        custom=None,
        default="",
        append=None,
    )
    assert result == ""


# Coordinator prompt tests

def test_get_coordinator_system_prompt():
    """Test coordinator system prompt is not empty."""
    prompt = get_coordinator_system_prompt()
    assert prompt
    assert "coordinator" in prompt.lower() or "orchestrating" in prompt.lower()


def test_prompt_manager_get_coordinator_prompt(prompt_manager):
    """Test PromptManager gets coordinator prompt."""
    prompt = prompt_manager.get_coordinator_prompt()
    assert prompt
    assert "coordinator" in prompt.lower() or "orchestrating" in prompt.lower()


# Git status tests

def test_get_git_status():
    """Test git status retrieval returns a dictionary."""
    status = get_git_status(Path("/home/s/code/my_claude/claude-core"))
    assert isinstance(status, dict)
    # May be empty if not a git repo or on CI
    assert "branch" in status or "status" in status or "recent_commits" in status or status == {}


def test_build_git_context_section_empty():
    """Test git context section with empty status."""
    result = build_git_context_section({})
    assert result == ""


def test_build_git_context_section_with_data():
    """Test git context section with git data."""
    git_status = {
        "branch": "main",
        "status": ["M  file1.py", "?? file2.py"],
        "recent_commits": ["abc123 Feature A", "def456 Feature B"],
    }
    result = build_git_context_section(git_status)
    assert "main" in result
    assert "file1.py" in result
    assert "file2.py" in result
    assert "Feature A" in result


# CLAUDE.md discovery tests

def test_get_claude_mds_empty_project(tmp_path):
    """Test CLAUDE.md discovery with no files."""
    mds = get_claude_mds(tmp_path)
    assert mds == []


def test_get_claude_mds_finds_file(tmp_path):
    """Test CLAUDE.md discovery finds files."""
    (tmp_path / "CLAUDE.md").write_text("# Project Instructions\n\nTest content.")
    mds = get_claude_mds(tmp_path)
    assert len(mds) == 1
    assert "Test content" in mds[0]


def test_get_claude_mds_nested(tmp_path):
    """Test CLAUDE.md discovery finds nested files."""
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (tmp_path / "CLAUDE.md").write_text("Root CLAUDE.md")
    (subdir / "CLAUDE.md").write_text("Nested CLAUDE.md")
    mds = get_claude_mds(tmp_path)
    assert len(mds) == 2


def test_build_claude_md_section_empty():
    """Test CLAUDE.md section with empty list."""
    result = build_claude_md_section([])
    assert result == ""


def test_build_claude_md_section_with_content():
    """Test CLAUDE.md section with content."""
    mds = ["# CLAUDE.md 1\n\nContent 1", "# CLAUDE.md 2\n\nContent 2"]
    result = build_claude_md_section(mds)
    assert "Content 1" in result
    assert "Content 2" in result


# PromptManager priority integration tests

def test_prompt_manager_build_effective_prompt(prompt_manager):
    """Test PromptManager build_effective_prompt with priority."""
    result = prompt_manager.build_effective_prompt(
        agent="Agent prompt",
        custom="Custom prompt",
    )
    assert result == "Agent prompt"


def test_prompt_manager_build_effective_prompt_default(prompt_manager):
    """Test PromptManager uses active template as default."""
    result = prompt_manager.build_effective_prompt()
    assert result == prompt_manager.get_active_template()


def test_prompt_manager_get_claude_mds(prompt_manager, tmp_path):
    """Test PromptManager CLAUDE.md discovery."""
    (tmp_path / "CLAUDE.md").write_text("Test")
    mds = prompt_manager.get_claude_mds(tmp_path)
    assert len(mds) == 1


def test_prompt_manager_get_git_context(prompt_manager):
    """Test PromptManager git context."""
    ctx = prompt_manager.get_git_context(Path("/home/s/code/my_claude/claude-core"))
    assert isinstance(ctx, dict)


def test_prompt_manager_build_git_context(prompt_manager):
    """Test PromptManager build git context section."""
    result = prompt_manager.build_git_context(Path("/home/s/code/my_claude/claude-core"))
    assert isinstance(result, str)


def test_prompt_manager_build_claude_md_context(prompt_manager, tmp_path):
    """Test PromptManager build CLAUDE.md context section."""
    (tmp_path / "CLAUDE.md").write_text("Test content")
    result = prompt_manager.build_claude_md_context(tmp_path)
    assert "Test content" in result