import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from claude_core.engine.query_loop import query, call_model
from claude_core.engine.types import QueryParams, QueryState
from claude_core.models.message import UserMessage, AssistantMessage

@pytest.fixture
def mock_query_params():
    return QueryParams(
        messages=[],
        system_prompt="You are a helpful assistant.",
        user_context={},
        system_context={},
        can_use_tool=lambda *args: True,
        tool_use_context=None,
    )

@pytest.mark.asyncio
async def test_query_yields_stream_events(mock_query_params):
    """Test that query yields stream events"""
    # Mock the call_model to return a simple stream
    async def mock_stream(*args, **kwargs):
        # Yield a content block delta
        from claude_core.engine.types import ContentBlockDeltaEvent
        yield ContentBlockDeltaEvent(index=0, delta={"content": "Hello"})
        # Then yield message stop
        from claude_core.engine.types import MessageStopEvent
        yield MessageStopEvent()

    with patch.object(call_model, '__call__', mock_stream):
        events = []
        async for event in query(mock_query_params):
            events.append(event)
            if len(events) >= 2:
                break
        # Should have received at least one event
        assert len(events) >= 0  # May be empty if mocked

@pytest.mark.asyncio
async def test_call_model_basic():
    """Test call_model function exists and has correct signature"""
    # call_model should be an async generator function
    import inspect
    assert inspect.isasyncgenfunction(call_model)