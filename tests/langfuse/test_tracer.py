"""Tests for Langfuse tracer."""

import pytest
from unittest.mock import MagicMock, patch


class TestNoOpTracer:
    """Tests for the NoOpTracer implementation."""

    def test_create_trace_returns_none(self):
        from claude_core.langfuse import NoOpTracer

        tracer = NoOpTracer()
        result = tracer.create_trace("session-1", "gpt-4o", [{"role": "user", "content": "hello"}])
        assert result is None

    def test_end_trace_does_nothing(self):
        from claude_core.langfuse import NoOpTracer

        tracer = NoOpTracer()
        # Should not raise
        tracer.end_trace(None, usage={"input_tokens": 100}, status="success")

    def test_create_tool_batch_span_returns_none(self):
        from claude_core.langfuse import NoOpTracer

        tracer = NoOpTracer()
        result = tracer.create_tool_batch_span(None, ["tool1", "tool2"])
        assert result is None

    def test_end_tool_batch_span_does_nothing(self):
        from claude_core.langfuse import NoOpTracer

        tracer = NoOpTracer()
        # Should not raise
        tracer.end_tool_batch_span(None)


class TestLangfuseTracer:
    """Tests for the LangfuseTracer implementation."""

    def test_create_trace_calls_client(self):
        from claude_core.langfuse import LangfuseTracer

        mock_client = MagicMock()
        mock_client.create_trace.return_value = "mock-trace"

        tracer = LangfuseTracer(client=mock_client)
        result = tracer.create_trace("session-1", "gpt-4o", [{"role": "user", "content": "hello"}])

        mock_client.create_trace.assert_called_once_with(
            session_id="session-1",
            model="gpt-4o",
            input=[{"role": "user", "content": "hello"}],
            query_source=None,
        )
        assert result == "mock-trace"

    def test_create_trace_with_query_source(self):
        from claude_core.langfuse import LangfuseTracer

        mock_client = MagicMock()
        mock_client.create_trace.return_value = "mock-trace"

        tracer = LangfuseTracer(client=mock_client)
        tracer.create_trace("session-1", "gpt-4o", [], query_source="cli")

        mock_client.create_trace.assert_called_once_with(
            session_id="session-1",
            model="gpt-4o",
            input=[],
            query_source="cli",
        )

    def test_end_trace_calls_client(self):
        from claude_core.langfuse import LangfuseTracer

        mock_client = MagicMock()
        mock_trace = MagicMock()

        tracer = LangfuseTracer(client=mock_client)
        tracer.end_trace(mock_trace, usage={"input_tokens": 100}, status="success")

        mock_client.end_trace.assert_called_once_with(
            mock_trace, usage={"input_tokens": 100}, status="success"
        )

    def test_create_tool_batch_span_calls_client(self):
        from claude_core.langfuse import LangfuseTracer

        mock_client = MagicMock()
        mock_client.create_tool_batch_span.return_value = "mock-span"
        mock_trace = MagicMock()

        tracer = LangfuseTracer(client=mock_client)
        result = tracer.create_tool_batch_span(mock_trace, ["tool1", "tool2"])

        mock_client.create_tool_batch_span.assert_called_once_with(
            mock_trace, ["tool1", "tool2"]
        )
        assert result == "mock-span"

    def test_end_tool_batch_span_calls_client(self):
        from claude_core.langfuse import LangfuseTracer

        mock_client = MagicMock()
        mock_span = MagicMock()

        tracer = LangfuseTracer(client=mock_client)
        tracer.end_tool_batch_span(mock_span)

        mock_client.end_tool_batch_span.assert_called_once_with(mock_span)


class TestLangfuseClient:
    """Tests for the LangfuseClient."""

    def test_create_trace_without_langfuse(self):
        from claude_core.langfuse.client import LangfuseClient

        with patch("claude_core.langfuse.client.LangfuseClient._ensure_initialized"):
            client = LangfuseClient()
            client._client = None  # Simulate no langfuse available

            result = client.create_trace("session-1", "gpt-4o", [])
            assert result is None

    def test_create_trace_with_langfuse(self):
        from claude_core.langfuse.client import LangfuseClient

        mock_langfuse = MagicMock()
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace

        client = LangfuseClient()
        client._client = mock_langfuse
        client._initialized = True  # Prevent _ensure_initialized from running

        result = client.create_trace("session-1", "gpt-4o", [{"role": "user", "content": "hello"}])

        mock_langfuse.trace.assert_called_once_with(
            session_id="session-1",
            model="gpt-4o",
            input=[{"role": "user", "content": "hello"}],
        )
        assert result == mock_trace

    def test_end_trace_updates_trace(self):
        from claude_core.langfuse.client import LangfuseClient

        mock_langfuse = MagicMock()
        mock_trace = MagicMock()
        client = LangfuseClient()
        client._client = mock_langfuse
        client._initialized = True

        client.end_trace(mock_trace, usage={"input_tokens": 100}, status="success")

        # update is called twice: once with usage, once with status
        mock_trace.update.assert_any_call(usage={"input_tokens": 100})
        mock_trace.update.assert_any_call(status="success")

    def test_end_trace_without_client(self):
        from claude_core.langfuse.client import LangfuseClient

        client = LangfuseClient()
        client._client = None

        # Should not raise
        client.end_trace(None, usage={"input_tokens": 100})


class TestGetTracer:
    """Tests for the get_tracer function."""

    def test_get_tracer_returns_noop_when_langfuse_not_available(self):
        from claude_core.langfuse import get_tracer, NoOpTracer, _tracer

        # Reset global tracer
        import claude_core.langfuse
        claude_core.langfuse._tracer = None

        with patch("claude_core.langfuse.LangfuseTracer", side_effect=ImportError):
            tracer = get_tracer()
            assert isinstance(tracer, NoOpTracer)

    def test_set_tracer(self):
        from claude_core.langfuse import set_tracer, NoOpTracer, LangfuseTracer, get_tracer

        # Reset global tracer
        import claude_core.langfuse
        claude_core.langfuse._tracer = None

        mock_tracer = LangfuseTracer()
        set_tracer(mock_tracer)

        assert get_tracer() is mock_tracer

        # Reset
        claude_core.langfuse._tracer = None
