import pytest
import asyncio
import tempfile
import os
import time
from claude_core.tools.builtin.task import create_task_tools
from claude_core.tools.base import Tool
from claude_core.models.tool import ToolUseContext, ToolUseContextOptions
from claude_core.utils.abort import AbortController
from claude_core.tasks.types import BackgroundTaskTracker, create_task_state, TaskType, TaskStatus

@pytest.fixture
def context():
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    BackgroundTaskTracker.get_instance().clear()
    ctx = ToolUseContext(
        options=ToolUseContextOptions(
            tools=[],
            debug=False,
            main_loop_model="gpt-4o",
            task_store_path=tmp.name,
        ),
        abort_controller=AbortController(),
    )
    yield ctx
    BackgroundTaskTracker.get_instance().clear()
    if os.path.exists(tmp.name):
        os.unlink(tmp.name)

def test_task_tools_created():
    tools = create_task_tools()
    assert isinstance(tools, list)
    assert len(tools) == 4
    tool_names = [t.name for t in tools]
    assert "TaskCreate" in tool_names
    assert "TaskUpdate" in tool_names
    assert "TaskList" in tool_names
    assert "TaskGet" in tool_names

@pytest.mark.asyncio
async def test_task_create_basic(context):
    tools = create_task_tools()
    task_create = next(t for t in tools if t.name == "TaskCreate")
    result = await task_create.call(
        {"title": "Test task", "description": "A test task", "tool_use_id": "test-id"},
        context,
        lambda *args: True,
    )
    assert result.is_error is False
    assert "Test task" in result.content

@pytest.mark.asyncio
async def test_task_list_basic(context):
    tools = create_task_tools()
    task_list = next(t for t in tools if t.name == "TaskList")
    result = await task_list.call(
        {"tool_use_id": "test-id"},
        context,
        lambda *args: True,
    )
    assert result.is_error is False


@pytest.mark.asyncio
async def test_task_persistence_across_tool_instances(context):
    tools = create_task_tools()
    task_create = next(t for t in tools if t.name == "TaskCreate")
    create_result = await task_create.call(
        {"title": "Persistent task", "description": "Survives reload", "tool_use_id": "persist-id"},
        context,
        lambda *args: True,
    )

    assert create_result.is_error is False

    reloaded_tools = create_task_tools()
    task_list = next(t for t in reloaded_tools if t.name == "TaskList")
    list_result = await task_list.call(
        {"tool_use_id": "list-id"},
        context,
        lambda *args: True,
    )

    assert list_result.is_error is False
    assert "Persistent task" in list_result.content


@pytest.mark.asyncio
async def test_task_list_includes_background_tracker_tasks(context):
    tracker = BackgroundTaskTracker.get_instance()
    state = create_task_state(
        task_type=TaskType.BACKGROUND_AGENT,
        subject="Background sync",
        description="background work",
        agent_id="agent-bg",
        agent_name="subagent",
        model="gpt-4o",
        is_backgrounded=True,
    )
    state.status = TaskStatus.RUNNING.value
    state.started_at = time.time()
    tracker.add_state(state)

    tools = create_task_tools()
    task_list = next(t for t in tools if t.name == "TaskList")
    result = await task_list.call(
        {"tool_use_id": "bg-list"},
        context,
        lambda *args: True,
    )

    assert result.is_error is False
    assert state.id in result.content
    assert "Background sync" in result.content


@pytest.mark.asyncio
async def test_task_get_reads_background_tracker_task(context):
    tracker = BackgroundTaskTracker.get_instance()
    state = create_task_state(
        task_type=TaskType.BACKGROUND_AGENT,
        subject="Background inspect",
        description="tracker backed task",
        agent_id="agent-bg-get",
        agent_name="subagent",
        model="gpt-4o",
        is_backgrounded=True,
    )
    state.status = TaskStatus.COMPLETED.value
    state.result = "done"
    state.completed_at = time.time()
    tracker.add_state(state)

    tools = create_task_tools()
    task_get = next(t for t in tools if t.name == "TaskGet")
    result = await task_get.call(
        {"tool_use_id": "bg-get", "task_id": state.id},
        context,
        lambda *args: True,
    )

    assert result.is_error is False
    assert "Background inspect" in result.content
    assert state.id in result.content
