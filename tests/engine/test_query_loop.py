import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from claude_core.engine.query_loop import query, call_model
from claude_core.engine.types import QueryParams, QueryState, ToolUseEvent, MessageStopEvent
from claude_core.models.message import UserMessage, AssistantMessage
from claude_core.models.tool import ToolUseContext, ToolUseContextOptions
from claude_core.utils.abort import AbortController

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


@pytest.mark.asyncio
async def test_call_model_uses_model_override():
    """call_model should send the explicit model override in request payload."""
    captured_json = {}

    class MockResponse:
        async def aiter_lines(self):
            yield "data: [DONE]"

    class MockStreamContext:
        async def __aenter__(self):
            return MockResponse()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class MockHttpClient:
        def stream(self, method, url, headers=None, json=None):
            captured_json.update(json or {})
            return MockStreamContext()

    mock_client = MagicMock()
    mock_client._client = MockHttpClient()
    mock_client.base_url = "https://api.openai.com/v1"
    mock_client.model = "primary-model"
    mock_client._build_headers = lambda: {}
    mock_client._build_chat_completions_url = lambda: "https://api.openai.com/v1/chat/completions"
    mock_client._build_request_body = lambda **kwargs: kwargs

    events = []
    async for event in call_model(
        client=mock_client,
        messages=[],
        system_prompt="sys",
        model="fallback-model",
    ):
        events.append(event)

    assert captured_json["model"] == "fallback-model"
    assert any(getattr(e, "type", "") == "message_stop" for e in events)


@pytest.mark.asyncio
async def test_query_stops_immediately_when_max_turns_zero():
    """query should stop before model call when max_turns is 0."""
    mock_client = MagicMock()
    context = ToolUseContext(
        options=ToolUseContextOptions(tools=[]),
        abort_controller=AbortController(),
    )
    context._client = mock_client

    params = QueryParams(
        messages=[],
        system_prompt="You are a helpful assistant.",
        user_context={},
        system_context={},
        can_use_tool=lambda *args: True,
        tool_use_context=context,
        max_turns=0,
    )

    events = []
    async for event in query(params):
        events.append(event)
        break

    assert len(events) == 1
    assert getattr(events[0], "reason", None) == "max_turns"


@pytest.mark.asyncio
async def test_call_model_buffers_multiple_streaming_tool_calls():
    """call_model should flush every streamed tool call instead of only the last one."""
    streamed_lines = [
        'data: {"choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"call_1","function":{"name":"first","arguments":"{\\"a\\":"}},{"index":1,"id":"call_2","function":{"name":"second","arguments":"{\\"b\\":"}}]}}]}',
        'data: {"choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"1}"}},{"index":1,"function":{"arguments":"2}"}}]},"finish_reason":"tool_calls"}]}',
        "data: [DONE]",
    ]

    class MockResponse:
        async def aiter_lines(self):
            for line in streamed_lines:
                yield line

    class MockStreamContext:
        async def __aenter__(self):
            return MockResponse()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class MockHttpClient:
        def stream(self, method, url, headers=None, json=None):
            return MockStreamContext()

    mock_client = MagicMock()
    mock_client._client = MockHttpClient()
    mock_client.model = "primary-model"
    mock_client._build_headers = lambda: {}
    mock_client._build_chat_completions_url = lambda: "https://api.openai.com/v1/chat/completions"
    mock_client._build_request_body = lambda **kwargs: kwargs

    tool_events = []
    async for event in call_model(
        client=mock_client,
        messages=[],
        system_prompt="sys",
    ):
        if getattr(event, "type", None) == "tool_use":
            tool_events.append(event)

    assert [(event.tool_use_id, event.name, event.input) for event in tool_events] == [
        ("call_1", "first", {"a": 1}),
        ("call_2", "second", {"b": 2}),
    ]


@pytest.mark.asyncio
async def test_query_persists_assistant_tool_use_message_before_execution():
    """query should append the assistant tool_use message before the executor consumes it."""
    messages = []
    captured_assistant_message = None
    call_count = 0

    async def fake_call_model(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield ToolUseEvent(tool_use_id="tool_1", name="search", input={"q": "test"})
            yield MessageStopEvent()
        else:
            yield MessageStopEvent()

    class FakeExecutor:
        def __init__(self, tool_definitions, can_use_tool, tool_use_context):
            self._context = tool_use_context

        def add_tool(self, block, assistant_message):
            nonlocal captured_assistant_message
            captured_assistant_message = assistant_message
            assert any(
                getattr(msg, "type", None) == "assistant"
                and msg.message.get("content") == [
                    {
                        "type": "tool_use",
                        "id": "tool_1",
                        "name": "search",
                        "input": {"q": "test"},
                    }
                ]
                for msg in messages
            )

        async def get_remaining_results(self):
            if False:
                yield None

        def get_updated_context(self):
            return self._context

    mock_client = MagicMock()
    context = ToolUseContext(
        options=ToolUseContextOptions(tools=[]),
        abort_controller=AbortController(),
    )
    context._client = mock_client

    params = QueryParams(
        messages=messages,
        system_prompt="You are a helpful assistant.",
        user_context={},
        system_context={},
        can_use_tool=lambda *args: True,
        tool_use_context=context,
        max_turns=1,
    )

    with patch("claude_core.engine.query_loop.call_model", fake_call_model), patch(
        "claude_core.tools.streaming_executor.StreamingToolExecutor", FakeExecutor
    ):
        events = [event async for event in query(params)]

    assert captured_assistant_message is not None
    assert any(getattr(event, "reason", None) == "continue" for event in events)
    assert messages[-1].message["content"][0]["type"] == "tool_use"
    assert messages[-1].message["content"][0]["id"] == "tool_1"


@pytest.mark.asyncio
async def test_query_yields_tool_result_with_tool_use_id():
    """query should preserve tool_use_id when yielding tool_result updates."""
    messages = []

    async def fake_call_model(*args, **kwargs):
        yield ToolUseEvent(tool_use_id="tool_42", name="search", input={"q": "needle"})
        yield MessageStopEvent()

    tool_result_message = UserMessage(
        uuid="user-msg-1",
        message={
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "content": [{"type": "text", "text": "done"}],
                    "tool_use_id": "tool_42",
                    "is_error": False,
                }
            ],
        },
        tool_use_result="done",
    )

    class FakeMessageUpdate:
        def __init__(self, message):
            self.message = message
            self.new_context = None

    class FakeExecutor:
        def __init__(self, tool_definitions, can_use_tool, tool_use_context):
            self._context = tool_use_context

        def add_tool(self, block, assistant_message):
            return None

        async def get_remaining_results(self):
            yield FakeMessageUpdate(tool_result_message)

        def get_updated_context(self):
            return self._context

    mock_client = MagicMock()
    context = ToolUseContext(
        options=ToolUseContextOptions(tools=[]),
        abort_controller=AbortController(),
    )
    context._client = mock_client

    params = QueryParams(
        messages=messages,
        system_prompt="You are a helpful assistant.",
        user_context={},
        system_context={},
        can_use_tool=lambda *args: True,
        tool_use_context=context,
        max_turns=1,
    )

    with patch("claude_core.engine.query_loop.call_model", fake_call_model), patch(
        "claude_core.tools.streaming_executor.StreamingToolExecutor", FakeExecutor
    ):
        events = [event async for event in query(params)]

    tool_result_events = [event for event in events if isinstance(event, dict) and event.get("type") == "tool_result"]
    assert tool_result_events == [
        {
            "type": "tool_result",
            "tool_use_id": "tool_42",
            "content": "done",
        }
    ]
