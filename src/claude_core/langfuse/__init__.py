"""Langfuse tracing integration for Claude Core."""

from __future__ import annotations

from typing import Any, Optional

from claude_core.langfuse.client import (
    LangfuseClient,
    get_client,
    configure,
)


class LangfuseTracer:
    """
    Langfuse tracer for distributed tracing of LLM calls and tool execution.

    This tracer creates traces at query start, records tool execution observations,
    and properly ends traces on completion or abortion.
    """

    def __init__(self, client: Optional[LangfuseClient] = None):
        self._client = client or get_client()

    def create_trace(self, session_id: str, model: str, input: list,
                     query_source: str | None = None) -> Any:
        """
        Create a new trace for a query session.

        Args:
            session_id: Unique identifier for the session
            model: The model being used (e.g., "gpt-4o")
            input: List of input messages
            query_source: Optional source of the query

        Returns:
            The created trace object, or None if tracing is not available
        """
        return self._client.create_trace(
            session_id=session_id,
            model=model,
            input=input,
            query_source=query_source,
        )

    def end_trace(self, trace: Any, usage: dict | None = None,
                  status: str | None = None) -> None:
        """
        End a trace with optional usage statistics.

        Args:
            trace: The trace object to end
            usage: Optional usage statistics (e.g., input_tokens, output_tokens)
            status: Optional status string (e.g., "success", "error")
        """
        self._client.end_trace(trace, usage=usage, status=status)

    def create_tool_batch_span(self, trace: Any, tool_names: list) -> Any:
        """
        Create a span for a batch of tool executions.

        Args:
            trace: The parent trace object
            tool_names: List of tool names being executed

        Returns:
            The created span object, or None if tracing is not available
        """
        return self._client.create_tool_batch_span(trace, tool_names)

    def end_tool_batch_span(self, span: Any) -> None:
        """
        End a tool batch span.

        Args:
            span: The span object to end
        """
        self._client.end_tool_batch_span(span)


class NoOpTracer:
    """
    No-op tracer that performs no operations.

    Used when Langfuse tracing is not enabled or available.
    """

    def create_trace(self, *args, **kwargs) -> None:
        """No-op trace creation."""
        return None

    def end_trace(self, *args, **kwargs) -> None:
        """No-op trace ending."""
        pass

    def create_tool_batch_span(self, *args, **kwargs) -> None:
        """No-op tool batch span creation."""
        return None

    def end_tool_batch_span(self, *args, **kwargs) -> None:
        """No-op tool batch span ending."""
        pass


# Global tracer instance
_tracer: Optional[LangfuseTracer | NoOpTracer] = None


def get_tracer() -> LangfuseTracer | NoOpTracer:
    """
    Get or create the global tracer instance.

    Returns LangfuseTracer if Langfuse is available, otherwise NoOpTracer.
    """
    global _tracer
    if _tracer is None:
        # Try to use LangfuseTracer, fall back to NoOpTracer
        try:
            from langfuse import Langfuse  # noqa: F401
            _tracer = LangfuseTracer()
        except ImportError:
            _tracer = NoOpTracer()
    return _tracer


def set_tracer(tracer: LangfuseTracer | NoOpTracer) -> None:
    """Set the global tracer instance."""
    global _tracer
    _tracer = tracer


__all__ = [
    "LangfuseTracer",
    "NoOpTracer",
    "LangfuseClient",
    "get_tracer",
    "set_tracer",
    "get_client",
    "configure",
]
