"""Task state models for subagent and background agent execution."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

_UNSET = object()


class TaskType(Enum):
    """Supported task categories."""

    LOCAL_SHELL = "local_shell"
    LOCAL_AGENT = "local_agent"
    SUBAGENT = "subagent"
    BACKGROUND_AGENT = "background_agent"


class TaskStatus(Enum):
    """Task lifecycle states."""

    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskState:
    """Base task state shared by all task kinds."""

    id: str
    task_type: TaskType
    status: str
    subject: str
    description: str
    owner: Optional[str] = None
    created_at: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[str] = None
    error: Optional[str] = None


@dataclass
class LocalShellTaskState(TaskState):
    """Task state for local shell execution."""

    command: str = ""
    working_dir: Optional[str] = None


@dataclass
class SubagentTaskState(TaskState):
    """Task state for foreground subagent execution."""

    agent_id: str = ""
    agent_name: str = ""
    model: str = "default"
    prompt: str = ""
    run_in_background: bool = False
    parent_agent_id: Optional[str] = None


@dataclass
class BackgroundAgentTaskState(TaskState):
    """Task state for background subagent execution."""

    agent_id: str = ""
    agent_name: str = ""
    model: str = "default"
    is_backgrounded: bool = True


def uuid_suffix() -> str:
    """Small random suffix for task IDs."""

    return uuid.uuid4().hex[:8]


def create_task_id() -> str:
    """Create a reasonably unique task identifier."""

    return f"task-{int(time.time() * 1000)}-{uuid_suffix()}"


def create_task_state(
    task_type: TaskType,
    subject: str,
    description: str = "",
    owner: Optional[str] = None,
    **kwargs: Any,
) -> TaskState:
    """Factory for creating typed task states."""

    task_id = create_task_id()
    common = dict(
        id=task_id,
        task_type=task_type,
        status=TaskStatus.PENDING.value,
        subject=subject,
        description=description,
        owner=owner,
        created_at=time.time(),
    )

    if task_type == TaskType.LOCAL_SHELL:
        return LocalShellTaskState(**common, **kwargs)
    if task_type == TaskType.BACKGROUND_AGENT:
        return BackgroundAgentTaskState(**common, **kwargs)
    if task_type == TaskType.SUBAGENT:
        return SubagentTaskState(**common, **kwargs)
    return TaskState(**common, **kwargs)


class BackgroundTaskTracker:
    """In-process tracker for task states and running asyncio tasks."""

    _instance: BackgroundTaskTracker | None = None

    def __init__(self) -> None:
        self._states: dict[str, TaskState] = {}
        self._tasks: dict[str, asyncio.Task[Any]] = {}

    @classmethod
    def get_instance(cls) -> BackgroundTaskTracker:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def add_state(self, state: TaskState) -> None:
        self._states[state.id] = state

    def update_status(self, task_id: str, status: TaskStatus | str) -> None:
        state = self.get_state(task_id)
        if state is None:
            return
        state.status = status.value if isinstance(status, TaskStatus) else status

    def list_states(self) -> list[TaskState]:
        return list(self._states.values())

    def get_state(self, task_id: str) -> Optional[TaskState]:
        return self._states.get(task_id)

    def get_state_by_agent(self, agent_id: str) -> Optional[TaskState]:
        return next(
            (state for state in self._states.values() if getattr(state, "agent_id", None) == agent_id),
            None,
        )

    def start_task(self, agent_id: str, task: asyncio.Task[Any]) -> None:
        self._tasks[agent_id] = task
        task.add_done_callback(lambda done_task: self._clear_task_handle(agent_id, done_task))

    def get_task(self, agent_id: str) -> Optional[asyncio.Task[Any]]:
        return self._tasks.get(agent_id)

    def is_running(self, agent_id: str) -> bool:
        task = self._tasks.get(agent_id)
        return task is not None and not task.done()

    def remove(self, agent_id: str) -> None:
        self._tasks.pop(agent_id, None)

    def update_state_for_agent(
        self,
        agent_id: str,
        *,
        status: str,
        result: Any = _UNSET,
        error: Any = _UNSET,
        completed_at: float | None = None,
    ) -> Optional[TaskState]:
        state = self.get_state_by_agent(agent_id)
        if state is None:
            return None

        state.status = status
        if result is not _UNSET:
            state.result = result
        if error is not _UNSET:
            state.error = error
        if completed_at is not None:
            state.completed_at = completed_at

        if status in {
            TaskStatus.STOPPED.value,
            TaskStatus.COMPLETED.value,
            TaskStatus.FAILED.value,
            TaskStatus.CANCELLED.value,
        }:
            self.remove(agent_id)
        return state

    def clear(self) -> None:
        self._states.clear()
        self._tasks.clear()

    def _clear_task_handle(self, agent_id: str, done_task: asyncio.Task[Any]) -> None:
        current = self._tasks.get(agent_id)
        if current is done_task:
            self._tasks.pop(agent_id, None)
