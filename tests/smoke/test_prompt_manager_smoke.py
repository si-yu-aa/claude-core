"""Smoke tests for Prompt/Context management.

These tests verify the basic functionality of prompt building and context management.
"""

import pytest
from claude_core.prompt.builder import SystemPromptBuilder, build_effective_prompt
from claude_core.context.manager import ContextManager, get_model_context_window, has_1m_context
from claude_core.context.project import (
    GitStatus,
    ProjectMetadata,
    PlatformInfo,
    get_working_directory,
    get_platform_info,
    build_system_context,
)


class TestPromptBuilder:
    """Smoke tests for PromptBuilder."""

    def test_builder_initialization(self):
        """Should initialize SystemPromptBuilder."""
        builder = SystemPromptBuilder(
            base_instructions="You are helpful.",
            tools=[],
        )
        assert builder is not None

    def test_build_effective_prompt(self):
        """Should build effective prompt with priority."""
        result = build_effective_prompt(
            override=None,
            coordinator=None,
            agent=None,
            custom=None,
            default="You are a default assistant.",
        )
        assert "default" in result

    def test_build_effective_prompt_with_override(self):
        """Should use override when provided."""
        result = build_effective_prompt(
            override="You are an override.",
            coordinator=None,
            agent=None,
            custom=None,
            default="You are a default assistant.",
        )
        assert "override" in result


class TestContextManager:
    """Smoke tests for ContextManager."""

    def test_context_manager_initialization(self):
        """Should initialize ContextManager."""
        manager = ContextManager(max_tokens=100000, model="gpt-4o")
        assert manager.model == "gpt-4o"

    def test_model_context_window(self):
        """Should return correct context windows."""
        assert get_model_context_window("gpt-4o") == 128000
        assert get_model_context_window("gpt-4") == 8192
        assert get_model_context_window("unknown-model") == 128000  # default

    def test_has_1m_context(self):
        """Should correctly identify 1M models."""
        # gpt-4o has 128000 context, not 1M
        assert has_1m_context("gpt-4o") is False
        assert has_1m_context("gpt-4") is False

    def test_budget_property(self):
        """Should have budget property."""
        manager = ContextManager(max_tokens=100000, model="gpt-4o")
        assert manager.budget is not None
        assert manager.budget.max_tokens == 100000

    def test_snip_compact_property(self):
        """Should have snip_compact property."""
        manager = ContextManager(max_tokens=100000, model="gpt-4o")
        assert manager.snip_compact is not None

    def test_auto_compact_property(self):
        """Should have auto_compact property."""
        manager = ContextManager(max_tokens=100000, model="gpt-4o")
        assert manager.auto_compact is not None


class TestProjectContext:
    """Smoke tests for project context utilities."""

    def test_get_working_directory(self):
        """Should return current working directory."""
        cwd = get_working_directory()
        assert cwd is not None
        assert len(cwd) > 0
        assert isinstance(cwd, str)

    def test_get_platform_info(self):
        """Should return platform info."""
        info = get_platform_info()
        assert isinstance(info, PlatformInfo)
        assert info.platform in ("linux", "darwin", "windows")
        assert info.cwd == get_working_directory()

    def test_build_system_context(self):
        """Should build system context."""
        context = build_system_context()
        assert isinstance(context, dict)

    def test_build_system_context_excludes(self):
        """Should respect exclude flags."""
        context = build_system_context(
            include_git=False,
            include_project=False,
            include_platform=False,
        )
        # Should only have env if include_env=True
        assert "git" not in context
        assert "project" not in context
        assert "platform" not in context


class TestGitStatus:
    """Smoke tests for GitStatus."""

    def test_git_status_creation(self):
        """Should create GitStatus."""
        status = GitStatus(
            branch="main",
            is_dirty=True,
            has_untracked_files=False,
            staged_files=["file1.txt"],
            modified_files=[],
            deleted_files=[],
        )

        assert status.branch == "main"
        assert status.is_dirty is True
        assert len(status.staged_files) == 1


class TestProjectMetadata:
    """Smoke tests for ProjectMetadata."""

    def test_project_metadata_creation(self):
        """Should create ProjectMetadata."""
        metadata = ProjectMetadata(
            name="test-project",
            version="1.0.0",
            description="A test project",
            has_readme=True,
            readme_path="/path/to/README.md",
            has_tsconfig=False,
            has_package_json=True,
            has_pyproject=False,
            has_requirements=False,
            has_git=True,
            repo_root="/path/to/repo",
        )

        assert metadata.name == "test-project"
        assert metadata.version == "1.0.0"
        assert metadata.has_readme is True
        assert metadata.has_package_json is True
