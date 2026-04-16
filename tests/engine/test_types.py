import pytest
from claude_core.engine.types import (
    QueryParams,
    QueryState,
    StreamEvent,
    ContentBlockDeltaEvent,
    MessageStopEvent,
    Continue,
    Stop,
)
from claude_core.engine.config import QueryEngineConfig

def test_query_params_creation():
    params = QueryParams(
        messages=[],
        system_prompt="You are a helpful assistant.",
        user_context={},
        system_context={},
        can_use_tool=lambda *args: True,
        tool_use_context=None,
    )
    assert params.system_prompt == "You are a helpful assistant."
    assert params.messages == []

def test_query_state_defaults():
    state = QueryState(
        messages=[],
        tool_use_context=None,
    )
    assert state.turn_count == 1
    assert state.max_output_tokens_recovery_count == 0
    assert state.has_attempted_reactive_compact is False

def test_stream_event_types():
    delta = ContentBlockDeltaEvent(index=0, delta={"content": "Hello"})
    assert delta.type == "content_block_delta"
    assert delta.index == 0

    stop = MessageStopEvent()
    assert stop.type == "message_stop"

def test_continue_transition():
    cont = Continue()
    assert cont.reason == "continue"

def test_stop_transition():
    stop = Stop(reason="stop")
    assert stop.reason == "stop"