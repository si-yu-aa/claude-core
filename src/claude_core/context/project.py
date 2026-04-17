"""Project context utilities."""

from __future__ import annotations

import os
import platform
import socket
from dataclasses import dataclass
from typing import Optional


@dataclass
class GitStatus:
    """Git repository status."""
    branch: str
    is_dirty: bool
    has_untracked_files: bool
    staged_files: list[str]
    modified_files: list[str]
    deleted_files: list[str]


@dataclass
class PlatformInfo:
    """Platform information."""
    platform: str  # linux, darwin, windows
    hostname: str
    cwd: str
    python_version: str


@dataclass
class ProjectMetadata:
    """Project metadata."""
    name: str
    version: str
    description: str
    has_readme: bool
    readme_path: Optional[str]
    has_tsconfig: bool
    has_package_json: bool
    has_pyproject: bool
    has_requirements: bool
    has_git: bool
    repo_root: Optional[str]


def get_working_directory() -> str:
    """Get the current working directory."""
    return os.getcwd()


def get_platform_info() -> PlatformInfo:
    """Get platform information."""
    return PlatformInfo(
        platform=platform.system().lower(),
        hostname=socket.gethostname(),
        cwd=get_working_directory(),
        python_version=platform.python_version(),
    )


def build_system_context(
    include_git: bool = True,
    include_project: bool = True,
    include_platform: bool = True,
    include_env: bool = False,
) -> dict:
    """Build system context dictionary."""
    context = {}

    if include_platform:
        info = get_platform_info()
        context["platform"] = {
            "os": info.platform,
            "hostname": info.hostname,
            "cwd": info.cwd,
        }

    if include_git:
        context["git"] = {
            "branch": "main",
            "is_dirty": False,
        }

    if include_project:
        context["project"] = {
            "name": "claude-core",
            "has_readme": True,
        }

    return context