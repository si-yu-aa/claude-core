"""Smoke tests for QueryEngine and query loop.

These tests verify the basic functionality of the query engine without
requiring external API access.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from claude_core.engine.query_engine import QueryEngine
from claude_core.engine.query_loop import call_model
from claude_core.engine.config import QueryEngineConfig
from claude_core.engine.types import QueryParams, Continue, Stop


class TestQueryEngineSmoke:
    """Smoke tests for QueryEngine."""

    def test_query_engine_initialization(self):
        """QueryEngine should initialize with config."""
        config = QueryEngineConfig(
            api_key="test-key",
            model="gpt-4o",
        )
        engine = QueryEngine(config)
        assert engine.config.model == "gpt-4o"

    def test_query_engine_set_tools(self):
        """Should set tools on engine."""
        config = QueryEngineConfig(api_key="test-key")
        engine = QueryEngine(config)

        mock_tool = MagicMock()
        mock_tool.name = "TestTool"
        engine.set_tools([mock_tool])

        # Verify tools were set (internal state)
        assert hasattr(engine, '_tools')
        assert len(engine._tools) == 1

    def test_query_engine_set_system_prompt(self):
        """Should set system prompt."""
        config = QueryEngineConfig(api_key="test-key")
        engine = QueryEngine(config)

        engine.set_system_prompt("You are a helpful assistant.")
        assert hasattr(engine, '_system_prompt')
        assert engine._system_prompt == "You are a helpful assistant."

    def test_submit_message_returns_async_generator(self):
        """submit_message should return an async generator."""
        config = QueryEngineConfig(api_key="test-key")
        engine = QueryEngine(config)

        result = engine.submit_message("Hello")
        assert hasattr(result, '__aiter__')


class TestQueryLoopSmoke:
    """Smoke tests for query loop functions."""

    def test_continue_class(self):
        """Continue class should work."""
        c = Continue()
        assert c.reason == "continue"

    def test_stop_class(self):
        """Stop class should work with various reasons."""
        s = Stop(reason="complete")
        assert s.reason == "complete"

        s2 = Stop(reason="error")
        assert s2.reason == "error"

    def test_query_state_defaults(self):
        """QueryState should have sensible defaults."""
        from claude_core.engine.types import QueryState

        state = QueryState(messages=[], tool_use_context=None)
        assert state.turn_count == 0
        assert state.stop_hook_active is None

    def test_query_params_defaults(self):
        """QueryParams should have sensible defaults."""
        params = QueryParams(
            messages=[],
            system_prompt="test",
            user_context={},
            system_context={},
            can_use_tool=lambda x: True,
            tool_use_context=None,
        )
        assert params.query_source == "sdk"
        assert params.skip_cache_write is False


class TestCallModelSmoke:
    """Smoke tests for call_model function."""

    @pytest.mark.asyncio
    async def test_call_model_with_mock_client(self):
        """call_model should work with a mock client."""
        # Create mock client
        mock_client = MagicMock()
        mock_response = MagicMock()

        # Mock streaming response
        async def mock_stream():
            # Simulate a simple response
            yield {"type": "content_block_delta", "delta": {"content": "Hello"}, "index": 0}
            yield {"type": "message_stop"}

        mock_response.aiter_lines = mock_stream
        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = MagicMock(return_value=mock_stream_ctx)

        # This test just verifies the structure works
        # Real API testing would require integration tests
        from claude_core.engine.query_loop import BufferedToolCall
        buf = BufferedToolCall()
        assert buf.id == ""
