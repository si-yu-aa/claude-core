"""Task types for agent background tasks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
import uuid


class TaskType(Enum):
    """Types of background tasks."""
    LOCAL_SHELL = "local_shell"
    SUBAGENT = "subagent"
    LOCAL_AGENT = "local_agent"


class TaskStatus(Enum):
    """Status of a background task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class LocalShellTaskState:
    """State for local shell task."""
    task_type: TaskType = TaskType.LOCAL_SHELL
    subject: str = ""
    command: str = ""
    working_dir: Optional[str] = None


@dataclass
class SubagentTaskState:
    """State for subagent task."""
    task_type: TaskType = TaskType.SUBAGENT
    subject: str = ""
    agent_name: str = ""
    run_in_background: bool = False
    parent_agent_id: Optional[str] = None


@dataclass
class TaskState:
    """Generic task state container."""
    id: str
    task_type: TaskType
    subject: str
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


def create_task_id() -> str:
    """Create a unique task ID."""
    return f"task_{uuid.uuid4().hex[:12]}"


def create_task_state(
    task_type: TaskType,
    subject: str,
    **kwargs
) -> TaskState:
    """Create a task state with the given type."""
    task_id = create_task_id()

    if task_type == TaskType.LOCAL_SHELL:
        state = LocalShellTaskState(
            task_type=task_type,
            subject=subject,
            command=kwargs.get("command", ""),
            working_dir=kwargs.get("working_dir"),
        )
    elif task_type == TaskType.SUBAGENT:
        state = SubagentTaskState(
            task_type=task_type,
            subject=subject,
            agent_name=kwargs.get("agent_name", ""),
            run_in_background=kwargs.get("run_in_background", False),
            parent_agent_id=kwargs.get("parent_agent_id"),
        )
    else:
        state = TaskState(
            id=task_id,
            task_type=task_type,
            subject=subject,
        )
        return state

    # Add common fields
    state.id = task_id
    return state


class BackgroundTaskTracker:
    """Tracker for background tasks (singleton)."""

    _instance = None

    def __init__(self):
        self._tasks: dict[str, TaskState] = {}

    @classmethod
    def get_instance(cls) -> BackgroundTaskTracker:
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def add_state(self, state: TaskState) -> None:
        """Add a task state to the tracker."""
        self._tasks[state.id] = state

    def get_state(self, task_id: str) -> TaskState | None:
        """Get a task state by ID."""
        return self._tasks.get(task_id)

    def is_running(self, task_id: str) -> bool:
        """Check if a task is running."""
        state = self.get_state(task_id)
        return state is not None and state.status == TaskStatus.RUNNING

    def update_status(self, task_id: str, status: TaskStatus) -> None:
        """Update task status."""
        state = self.get_state(task_id)
        if state:
            state.status = status