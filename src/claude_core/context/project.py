"""Project/system context helpers used by smoke tests and prompt assembly."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import platform
import socket
import subprocess


@dataclass
class GitStatus:
    branch: str | None = None
    is_dirty: bool = False
    has_untracked_files: bool = False
    staged_files: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    deleted_files: list[str] = field(default_factory=list)


@dataclass
class ProjectMetadata:
    name: str
    version: str | None = None
    description: str | None = None
    has_readme: bool = False
    readme_path: str | None = None
    has_tsconfig: bool = False
    has_package_json: bool = False
    has_pyproject: bool = False
    has_requirements: bool = False
    has_git: bool = False
    repo_root: str | None = None


@dataclass
class PlatformInfo:
    platform: str
    python_version: str
    cwd: str
    hostname: str = ""


def get_working_directory() -> str:
    return os.getcwd()


def get_platform_info() -> PlatformInfo:
    return PlatformInfo(
        platform=platform.system().lower(),
        python_version=platform.python_version(),
        cwd=get_working_directory(),
        hostname=socket.gethostname(),
    )


def _get_git_status(cwd: str) -> GitStatus | None:
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if branch.returncode != 0 or status.returncode != 0:
        return None

    lines = [line for line in status.stdout.splitlines() if line.strip()]
    return GitStatus(
        branch=branch.stdout.strip() or None,
        is_dirty=bool(lines),
        has_untracked_files=any(line.startswith("??") for line in lines),
        staged_files=[line[3:] for line in lines if line[:2].strip()],
        modified_files=[line[3:] for line in lines if line.startswith(" M")],
        deleted_files=[line[3:] for line in lines if "D" in line[:2]],
    )


def _get_project_metadata(cwd: str) -> ProjectMetadata:
    root = Path(cwd)
    readme = next(iter([p for p in (root / "README.md", root / "readme.md") if p.exists()]), None)
    return ProjectMetadata(
        name=root.name,
        has_readme=readme is not None,
        readme_path=str(readme) if readme else None,
        has_tsconfig=(root / "tsconfig.json").exists(),
        has_package_json=(root / "package.json").exists(),
        has_pyproject=(root / "pyproject.toml").exists(),
        has_requirements=(root / "requirements.txt").exists(),
        has_git=(root / ".git").exists(),
        repo_root=str(root),
    )


def build_system_context(
    include_git: bool = True,
    include_project: bool = True,
    include_platform: bool = True,
    include_env: bool = True,
) -> dict:
    cwd = get_working_directory()
    context: dict = {}
    if include_git:
        git = _get_git_status(cwd)
        if git is not None:
            context["git"] = git
    if include_project:
        context["project"] = _get_project_metadata(cwd)
    if include_platform:
        context["platform"] = get_platform_info()
    if include_env:
        context["env"] = {"cwd": cwd}
    return context
