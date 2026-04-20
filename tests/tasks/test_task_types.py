from claude_core.tasks.types import (
    BackgroundTaskTracker,
    TaskStatus,
    TaskType,
    create_task_state,
)


def test_create_task_state_subagent():
    state = create_task_state(
        task_type=TaskType.SUBAGENT,
        subject="hello",
        description="desc",
        agent_id="agent-1",
        agent_name="worker",
        model="gpt-4o",
        prompt="do thing",
    )
    assert state.task_type == TaskType.SUBAGENT
    assert state.status == TaskStatus.PENDING.value
    assert state.agent_id == "agent-1"


def test_background_task_tracker_add_and_get_state():
    tracker = BackgroundTaskTracker.get_instance()
    state = create_task_state(
        task_type=TaskType.BACKGROUND_AGENT,
        subject="bg",
        description="background task",
        agent_id="agent-bg",
        agent_name="subagent",
        model="gpt-4o",
        is_backgrounded=True,
    )
    tracker.add_state(state)
    assert tracker.get_state(state.id) is state
