"""Task management tools."""

from __future__ import annotations

from typing import Callable, TYPE_CHECKING, Optional
from dataclasses import dataclass
from datetime import datetime
import json
import os
import uuid

from claude_core.tools.base import Tool, ToolResult, build_tool
from claude_core.tasks.types import BackgroundTaskTracker, TaskState

if TYPE_CHECKING:
    from claude_core.models.tool import ToolUseContext

@dataclass
class Task:
    """Task data structure."""
    id: str
    title: str
    description: str = ""
    status: str = "pending"  # pending, in_progress, completed
    priority: str = "medium"  # low, medium, high
    created_at: str = ""
    updated_at: str = ""

def _get_current_time() -> str:
    return datetime.now().isoformat()

def _generate_task_id() -> str:
    return f"task_{uuid.uuid4().hex[:8]}"


def _get_task_store_path(context: "ToolUseContext") -> str:
    custom_path = getattr(getattr(context, "options", None), "task_store_path", None)
    if custom_path:
        return custom_path
    return os.path.expanduser("~/.codex/claude-core/tasks.json")


def _load_tasks(context: "ToolUseContext") -> dict[str, dict]:
    store_path = _get_task_store_path(context)
    if not os.path.exists(store_path):
        return {}
    try:
        with open(store_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _save_tasks(context: "ToolUseContext", tasks: dict[str, dict]) -> None:
    store_path = _get_task_store_path(context)
    parent = os.path.dirname(store_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(store_path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, sort_keys=True)


def _task_state_to_record(state: TaskState) -> dict[str, str | None]:
    return {
        "id": state.id,
        "title": state.subject,
        "description": state.description,
        "status": state.status,
        "priority": "medium",
        "created_at": datetime.fromtimestamp(state.created_at).isoformat() if state.created_at else "",
        "updated_at": datetime.fromtimestamp(
            state.completed_at or state.started_at or state.created_at
        ).isoformat() if (state.completed_at or state.started_at or state.created_at) else "",
        "task_type": state.task_type.value,
        "owner": state.owner,
        "result": state.result,
        "error": state.error,
        "agent_id": getattr(state, "agent_id", None),
        "agent_name": getattr(state, "agent_name", None),
        "model": getattr(state, "model", None),
    }


def _get_all_tasks(context: "ToolUseContext") -> dict[str, dict]:
    tasks = dict(_load_tasks(context))
    tracker = BackgroundTaskTracker.get_instance()
    for state in tracker.list_states():
        tasks[state.id] = _task_state_to_record(state)
    return tasks

def create_task_tools() -> list[Tool]:
    """Create all task-related tools."""

    def task_create_impl(args: dict, context: "ToolUseContext") -> ToolResult:
        title = args.get("title", "")
        description = args.get("description", "")
        priority = args.get("priority", "medium")
        tool_use_id = args.get("tool_use_id", "")

        if not title:
            return ToolResult(
                tool_use_id=tool_use_id,
                content="Error: title is required",
                is_error=True,
            )

        tasks = _load_tasks(context)
        task_id = _generate_task_id()
        task = Task(
            id=task_id,
            title=title,
            description=description,
            priority=priority,
            created_at=_get_current_time(),
            updated_at=_get_current_time(),
        )
        tasks[task_id] = {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "priority": task.priority,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }
        _save_tasks(context, tasks)

        return ToolResult(
            tool_use_id=tool_use_id,
            content=f"Created task: {title} (ID: {task_id})",
            is_error=False,
        )

    def task_update_impl(args: dict, context: "ToolUseContext") -> ToolResult:
        task_id = args.get("task_id", "")
        title = args.get("title")
        description = args.get("description")
        status = args.get("status")
        priority = args.get("priority")
        tool_use_id = args.get("tool_use_id", "")
        tasks = _load_tasks(context)

        if not task_id or task_id not in tasks:
            return ToolResult(
                tool_use_id=tool_use_id,
                content=f"Error: Task not found: {task_id}",
                is_error=True,
            )

        task = tasks[task_id]
        if title:
            task["title"] = title
        if description is not None:
            task["description"] = description
        if status:
            if status not in ("pending", "in_progress", "completed"):
                return ToolResult(
                    tool_use_id=tool_use_id,
                    content=f"Error: Invalid status. Must be: pending, in_progress, completed",
                    is_error=True,
                )
            task["status"] = status
        if priority:
            if priority not in ("low", "medium", "high"):
                return ToolResult(
                    tool_use_id=tool_use_id,
                    content=f"Error: Invalid priority. Must be: low, medium, high",
                    is_error=True,
                )
            task["priority"] = priority
        task["updated_at"] = _get_current_time()
        _save_tasks(context, tasks)

        return ToolResult(
            tool_use_id=tool_use_id,
            content=f"Updated task: {task['title']}",
            is_error=False,
        )

    def task_list_impl(args: dict, context: "ToolUseContext") -> ToolResult:
        status_filter = args.get("status")
        tool_use_id = args.get("tool_use_id", "")

        tasks = list(_get_all_tasks(context).values())
        if status_filter:
            tasks = [t for t in tasks if t["status"] == status_filter]

        if not tasks:
            return ToolResult(
                tool_use_id=tool_use_id,
                content="No tasks found",
                is_error=False,
            )

        lines = [f"Tasks ({len(tasks)}):"]
        for task in tasks:
            lines.append(f"  [{task['status']}] {task['id']}: {task['title']} ({task['priority']})")
            if task["description"]:
                lines.append(f"       {task['description'][:50]}...")

        return ToolResult(
            tool_use_id=tool_use_id,
            content="\n".join(lines),
            is_error=False,
        )

    def task_get_impl(args: dict, context: "ToolUseContext") -> ToolResult:
        task_id = args.get("task_id", "")
        tool_use_id = args.get("tool_use_id", "")
        tasks = _get_all_tasks(context)

        if not task_id:
            return ToolResult(
                tool_use_id=tool_use_id,
                content="Error: task_id is required",
                is_error=True,
            )

        if task_id not in tasks:
            return ToolResult(
                tool_use_id=tool_use_id,
                content=f"Error: Task not found: {task_id}",
                is_error=True,
            )

        task = tasks[task_id]
        lines = [
            f"Task: {task['title']}",
            f"ID: {task['id']}",
            f"Status: {task['status']}",
            f"Priority: {task['priority']}",
            f"Description: {task['description'] or '(none)'}",
            f"Created: {task['created_at']}",
            f"Updated: {task['updated_at']}",
        ]
        if task.get("task_type"):
            lines.append(f"Type: {task['task_type']}")
        if task.get("agent_id"):
            lines.append(f"Agent ID: {task['agent_id']}")
        if task.get("result"):
            lines.append(f"Result: {task['result']}")
        if task.get("error"):
            lines.append(f"Error: {task['error']}")

        return ToolResult(
            tool_use_id=tool_use_id,
            content="\n".join(lines),
            is_error=False,
        )

    def async_wrapper(func):
        async def call(args, context, can_use_tool, on_progress=None):
            return func(args, context)
        return call

    return [
        build_tool({
            "name": "TaskCreate",
            "description": "Create a new task",
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Task title"},
                    "description": {"type": "string", "description": "Task description"},
                    "priority": {"type": "string", "description": "Priority: low, medium, high"},
                },
                "required": ["title"],
            },
            "call": async_wrapper(task_create_impl),
            "is_concurrency_safe": lambda args: False,
        }),
        build_tool({
            "name": "TaskUpdate",
            "description": "Update an existing task",
            "input_schema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task ID to update"},
                    "title": {"type": "string", "description": "New title"},
                    "description": {"type": "string", "description": "New description"},
                    "status": {"type": "string", "description": "Status: pending, in_progress, completed"},
                    "priority": {"type": "string", "description": "Priority: low, medium, high"},
                },
                "required": ["task_id"],
            },
            "call": async_wrapper(task_update_impl),
            "is_concurrency_safe": lambda args: False,
        }),
        build_tool({
            "name": "TaskList",
            "description": "List all tasks",
            "input_schema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter by status"},
                },
            },
            "call": async_wrapper(task_list_impl),
            "is_concurrency_safe": lambda args: True,
        }),
        build_tool({
            "name": "TaskGet",
            "description": "Get details of a specific task",
            "input_schema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task ID"},
                },
                "required": ["task_id"],
            },
            "call": async_wrapper(task_get_impl),
            "is_concurrency_safe": lambda args: True,
        }),
    ]
