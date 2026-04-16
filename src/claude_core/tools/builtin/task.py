"""Task management tools."""

from __future__ import annotations

from typing import Callable, TYPE_CHECKING, Optional
from dataclasses import dataclass
from datetime import datetime
import uuid

from claude_core.tools.base import Tool, ToolResult, build_tool

if TYPE_CHECKING:
    from claude_core.models.tool import ToolUseContext

# In-memory task storage (in production, this would be a database)
_tasks: dict[str, dict] = {}

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

def create_task_tools() -> list[Tool]:
    """Create all task-related tools."""

    def task_create_impl(args: dict) -> ToolResult:
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

        task_id = _generate_task_id()
        task = Task(
            id=task_id,
            title=title,
            description=description,
            priority=priority,
            created_at=_get_current_time(),
            updated_at=_get_current_time(),
        )
        _tasks[task_id] = {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "priority": task.priority,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }

        return ToolResult(
            tool_use_id=tool_use_id,
            content=f"Created task: {title} (ID: {task_id})",
            is_error=False,
        )

    def task_update_impl(args: dict) -> ToolResult:
        task_id = args.get("task_id", "")
        title = args.get("title")
        description = args.get("description")
        status = args.get("status")
        priority = args.get("priority")
        tool_use_id = args.get("tool_use_id", "")

        if not task_id or task_id not in _tasks:
            return ToolResult(
                tool_use_id=tool_use_id,
                content=f"Error: Task not found: {task_id}",
                is_error=True,
            )

        task = _tasks[task_id]
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

        return ToolResult(
            tool_use_id=tool_use_id,
            content=f"Updated task: {task['title']}",
            is_error=False,
        )

    def task_list_impl(args: dict) -> ToolResult:
        status_filter = args.get("status")
        tool_use_id = args.get("tool_use_id", "")

        tasks = list(_tasks.values())
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

    def task_get_impl(args: dict) -> ToolResult:
        task_id = args.get("task_id", "")
        tool_use_id = args.get("tool_use_id", "")

        if not task_id:
            return ToolResult(
                tool_use_id=tool_use_id,
                content="Error: task_id is required",
                is_error=True,
            )

        if task_id not in _tasks:
            return ToolResult(
                tool_use_id=tool_use_id,
                content=f"Error: Task not found: {task_id}",
                is_error=True,
            )

        task = _tasks[task_id]
        lines = [
            f"Task: {task['title']}",
            f"ID: {task['id']}",
            f"Status: {task['status']}",
            f"Priority: {task['priority']}",
            f"Description: {task['description'] or '(none)'}",
            f"Created: {task['created_at']}",
            f"Updated: {task['updated_at']}",
        ]

        return ToolResult(
            tool_use_id=tool_use_id,
            content="\n".join(lines),
            is_error=False,
        )

    def async_wrapper(func):
        async def call(args, context, can_use_tool, on_progress=None):
            return func(args)
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