"""Tests for context compression strategies."""

import pytest
from claude_core.context.compression import (
    SnipResult,
    AutoCompactResult,
    snip_compact_if_needed,
    auto_compact,
    reactive_compact,
    snip_tokens_freed,
    yield_boundary_messages,
    extract_message_content,
    SnipCompact,
    AutoCompactStrategy,
    ReactiveCompact,
)


def create_message(content: str, msg_type: str = "user") -> object:
    """Helper to create a message object for testing."""
    return type('obj', (object,), {
        "uuid": f"uuid-{content[:10]}",
        "type": msg_type,
        "is_meta": False,
        "is_compact_summary": False,
        "message": {"content": content}
    })()


class TestExtractMessageContent:
    """Tests for extract_message_content function."""

    def test_extract_from_object_with_message(self):
        msg = create_message("Hello world")
        result = extract_message_content(msg)
        assert result == {"content": "Hello world"}

    def test_extract_from_dict(self):
        msg = {"content": "Hello world", "role": "user"}
        result = extract_message_content(msg)
        assert result == {"content": "Hello world", "role": "user"}

    def test_extract_from_string(self):
        msg = "Hello world"
        result = extract_message_content(msg)
        assert result == {"content": "Hello world"}


class TestSnipTokensFreed:
    """Tests for snip_tokens_freed function."""

    def test_tokens_freed_calculation(self):
        original = [create_message("Hello"), create_message("World")]
        remaining = [create_message("Hello")]
        freed = snip_tokens_freed(original, remaining, "")
        assert freed > 0

    def test_no_tokens_freed_when_same(self):
        original = [create_message("Hello")]
        remaining = [create_message("Hello")]
        freed = snip_tokens_freed(original, remaining, "")
        assert freed == 0


class TestYieldBoundaryMessages:
    """Tests for yield_boundary_messages function."""

    def test_yields_boundary_message(self):
        removed = [create_message("Hello"), create_message("World")]
        boundaries = list(yield_boundary_messages(removed))
        assert len(boundaries) == 1
        assert "2 messages" in boundaries[0].message["content"]

    def test_empty_list_yields_nothing(self):
        boundaries = list(yield_boundary_messages([]))
        assert len(boundaries) == 0


class TestSnipCompactIfNeeded:
    """Tests for snip_compact_if_needed function."""

    def test_no_compaction_under_threshold(self):
        messages = [create_message("Short")]
        result = snip_compact_if_needed(messages, threshold=50000)
        assert result.messages == messages
        assert result.tokens_freed == 0

    def test_compaction_under_threshold_small_list(self):
        messages = [create_message("Short"), create_message("Message")]
        result = snip_compact_if_needed(messages, threshold=50000)
        # With less than 3 messages, no compaction
        assert result.tokens_freed == 0

    def test_compaction_over_threshold(self):
        # Create messages with enough content to exceed threshold
        long_content = "x" * 20000  # ~5000 tokens
        messages = [
            create_message("System prompt"),
            create_message(long_content),
            create_message(long_content),
            create_message(long_content),
            create_message("Recent message"),
            create_message("Recent message 2"),
        ]
        result = snip_compact_if_needed(messages, threshold=1000)
        assert result.tokens_freed > 0
        assert len(result.messages) < len(messages)
        assert result.boundary_message is not None


class TestAutoCompact:
    """Tests for auto_compact function."""

    def test_no_compaction_under_threshold(self):
        messages = [create_message("Short")]
        result = auto_compact(messages, "System prompt", threshold=80000)
        assert result.tokens_freed == 0
        assert result.messages == messages

    def test_compaction_over_threshold(self):
        long_content = "x" * 20000  # ~5000 tokens
        messages = [
            create_message(long_content),
            create_message(long_content),
            create_message(long_content),
            create_message("Recent"),
        ]
        result = auto_compact(messages, "System prompt", threshold=1000)
        assert result.tokens_freed > 0
        assert result.boundary_message is not None

    def test_boundary_message_contains_count(self):
        long_content = "x" * 20000
        messages = [
            create_message(long_content),
            create_message(long_content),
            create_message("Recent"),
        ]
        result = auto_compact(messages, "System", threshold=1000)
        assert result.boundary_message is not None
        assert "messages summarized" in result.boundary_message.message["content"]


class TestReactiveCompact:
    """Tests for reactive_compact function."""

    def test_413_error_triggers_compaction(self):
        assert reactive_compact([], "413 Payload Too Large") is True

    def test_context_length_error_triggers(self):
        assert reactive_compact([], "context_length_exceeded") is True

    def test_too_long_error_triggers(self):
        assert reactive_compact([], "messages_too_long") is True

    def test_max_tokens_error_triggers(self):
        assert reactive_compact([], "max_tokens exceeded") is True

    def test_unrelated_error_does_not_trigger(self):
        assert reactive_compact([], "connection timeout") is False

    def test_case_insensitive(self):
        assert reactive_compact([], "Context_Length") is True


class TestSnipCompactClass:
    """Tests for SnipCompact class."""

    def test_initialization(self):
        compact = SnipCompact(threshold=60000)
        assert compact.threshold == 60000

    def test_should_compact_under_threshold(self):
        compact = SnipCompact(threshold=50000)
        messages = [create_message("Short")]
        assert compact.should_compact(messages) is False

    def test_should_compact_over_threshold(self):
        compact = SnipCompact(threshold=1000)
        messages = [create_message("x" * 10000)]
        assert compact.should_compact(messages) is True

    def test_compact_method(self):
        compact = SnipCompact(threshold=1000)
        messages = [create_message("x" * 5000) for _ in range(5)]
        result = compact.compact(messages)
        assert isinstance(result, SnipResult)
        assert result.tokens_freed > 0


class TestAutoCompactStrategy:
    """Tests for AutoCompactStrategy class."""

    def test_initialization(self):
        strategy = AutoCompactStrategy(threshold=90000)
        assert strategy.threshold == 90000

    def test_should_compact_under_threshold(self):
        strategy = AutoCompactStrategy(threshold=50000)
        messages = [create_message("Short")]
        assert strategy.should_compact(messages, "System") is False

    def test_should_compact_over_threshold(self):
        strategy = AutoCompactStrategy(threshold=1000)
        messages = [create_message("x" * 10000)]
        assert strategy.should_compact(messages, "System") is True

    def test_compact_method(self):
        strategy = AutoCompactStrategy(threshold=1000)
        messages = [create_message("x" * 5000) for _ in range(3)]
        result = strategy.compact(messages, "System")
        assert isinstance(result, AutoCompactResult)
        assert result.tokens_freed > 0


class TestReactiveCompactClass:
    """Tests for ReactiveCompact class."""

    def test_should_compact_with_413(self):
        compact = ReactiveCompact()
        assert compact.should_compact("413 error") is True

    def test_should_compact_with_context_length(self):
        compact = ReactiveCompact()
        assert compact.should_compact("context_length_exceeded") is True

    def test_should_not_compact_with_other_error(self):
        compact = ReactiveCompact()
        assert compact.should_compact("connection refused") is False

    def test_compact_method(self):
        compact = ReactiveCompact()
        # Use longer content to exceed 60000 threshold
        messages = [create_message("x" * 200000) for _ in range(3)]
        result = compact.compact(messages, "System")
        assert isinstance(result, AutoCompactResult)
        assert result.tokens_freed > 0
