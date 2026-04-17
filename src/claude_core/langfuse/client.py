"""Langfuse client for distributed tracing."""

from __future__ import annotations

from typing import Any, Optional
import os


class LangfuseClient:
    """Langfuse client for creating traces and spans."""

    def __init__(self, public_key: str | None = None, secret_key: str | None = None,
                 host: str | None = None):
        self._public_key = public_key or os.environ.get("LANGFUSE_PUBLIC_KEY")
        self._secret_key = secret_key or os.environ.get("LANGFUSE_SECRET_KEY")
        self._host = host or os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
        self._client = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of the Langfuse client."""
        if self._initialized:
            return

        try:
            from langfuse import Langfuse
            self._client = Langfuse(
                public_key=self._public_key,
                secret_key=self._secret_key,
                host=self._host,
            )
        except ImportError:
            self._client = None

        self._initialized = True

    def create_trace(self, session_id: str, model: str, input: list,
                     query_source: str | None = None) -> Any:
        """Create a new trace for a query session."""
        self._ensure_initialized()

        if self._client is None:
            return None

        trace_kwargs = {
            "session_id": session_id,
            "model": model,
            "input": input,
        }

        if query_source:
            trace_kwargs["query_source"] = query_source

        return self._client.trace(**trace_kwargs)

    def end_trace(self, trace: Any, usage: dict | None = None,
                  status: str | None = None) -> None:
        """End a trace with optional usage statistics."""
        if trace is None or self._client is None:
            return

        try:
            if usage:
                trace.update(usage=usage)
            if status:
                trace.update(status=status)
            else:
                trace.update(status="success")
        except Exception:
            pass

    def create_tool_batch_span(self, trace: Any, tool_names: list) -> Any:
        """Create a span for a batch of tool executions."""
        if trace is None or self._client is None:
            return None

        try:
            return trace.span(
                name="tool_batch",
                input={"tool_names": tool_names},
            )
        except Exception:
            return None

    def end_tool_batch_span(self, span: Any) -> None:
        """End a tool batch span."""
        if span is None:
            return

        try:
            span.update(status="success")
        except Exception:
            pass


# Singleton instance
_client: Optional[LangfuseClient] = None


def get_client() -> LangfuseClient:
    """Get or create the Langfuse client singleton."""
    global _client
    if _client is None:
        _client = LangfuseClient()
    return _client


def configure(public_key: str | None = None, secret_key: str | None = None,
              host: str | None = None) -> None:
    """Configure the Langfuse client with explicit credentials."""
    global _client
    _client = LangfuseClient(public_key=public_key, secret_key=secret_key, host=host)
