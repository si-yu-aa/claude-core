"""Context compression strategies for token management.

Implements multiple compaction strategies:
- SnipCompact: Removes middle messages, keeps recent/important
- AutoCompact: Threshold-triggered automatic compression
- ReactiveCompact: Compression triggered by 413 errors
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Callable, Iterator
from claude_core.utils.tokens import count_tokens, count_tokens_for_messages


@dataclass
class SnipResult:
    """Result of snip compaction operation."""
    messages: list[Any]
    tokens_freed: int
    boundary_message: Optional[Any] = None


@dataclass
class AutoCompactResult:
    """Result of auto compaction operation."""
    messages: list[Any]
    tokens_freed: int
    boundary_message: Optional[Any] = None


@dataclass
class CompactBoundary:
    """Boundary message that separates preserved from removed content."""
    content: str
    original_count: int
    preserved_count: int


def snip_tokens_freed(
    original_messages: list[Any],
    remaining_messages: list[Any],
    system_prompt: str
) -> int:
    """
    Calculate accurate token count freed by snip compaction.

    Args:
        original_messages: Messages before compaction
        remaining_messages: Messages after compaction
        system_prompt: The system prompt

    Returns:
        Number of tokens freed
    """
    original_tokens = count_tokens_for_messages([
        {"content": system_prompt},
        *[extract_message_content(m) for m in original_messages]
    ])

    remaining_tokens = count_tokens_for_messages([
        {"content": system_prompt},
        *[extract_message_content(m) for m in remaining_messages]
    ])

    return max(0, original_tokens - remaining_tokens)


def extract_message_content(msg: Any) -> dict:
    """Extract content dict from a message object."""
    if hasattr(msg, "message") and isinstance(getattr(msg, "message", None), dict):
        return msg.message
    elif isinstance(msg, dict):
        return msg
    else:
        return {"content": str(msg)}


def yield_boundary_messages(
    removed_messages: list[Any],
    boundary_marker: str = "[Previous messages removed]"
) -> Iterator[Any]:
    """
    Yield boundary messages to mark where content was removed.

    Args:
        removed_messages: Messages that were removed during compaction
        boundary_marker: Text to include in boundary message

    Yields:
        Boundary message objects
    """
    if not removed_messages:
        return

    total_removed = len(removed_messages)
    total_tokens = sum(
        count_tokens(extract_message_content(m).get("content", ""))
        for m in removed_messages
    )

    boundary_content = (
        f"{boundary_marker} "
        f"({total_removed} messages, ~{total_tokens} tokens)"
    )

    yield type('obj', (object,), {
        "uuid": "boundary-uuid",
        "type": "system",
        "is_meta": True,
        "is_compact_summary": True,
        "message": {"content": boundary_content}
    })()


def snip_compact_if_needed(
    messages: list[Any],
    threshold: int = 50000
) -> SnipResult:
    """
    Compact messages by removing middle messages if token count exceeds threshold.

    Uses HISTORY_SNIP strategy: keeps recent messages and removes middle portion
    while preserving boundary markers.

    Args:
        messages: List of messages to potentially compact
        threshold: Token count threshold for triggering compaction

    Returns:
        SnipResult with compacted messages and metadata
    """
    if len(messages) < 3:
        return SnipResult(
            messages=messages,
            tokens_freed=0,
            boundary_message=None
        )

    total_tokens = sum(
        count_tokens(extract_message_content(m).get("content", ""))
        for m in messages
    )

    if total_tokens <= threshold:
        return SnipResult(
            messages=messages,
            tokens_freed=0,
            boundary_message=None
        )

    # Keep first (system) and last N messages
    # Strategy: keep first message (usually system) and last 2/3 of remaining
    first_message = messages[0]
    remaining = messages[1:]

    # Keep last half of messages
    keep_count = max(1, len(remaining) // 2)
    kept_messages = remaining[-keep_count:]
    removed_messages = remaining[:-keep_count]

    # Create boundary message
    boundary_gen = yield_boundary_messages(
        removed_messages,
        f"[{len(removed_messages)} messages removed]"
    )
    boundary = next(boundary_gen, None)

    # Build result: first + boundary + kept
    result_messages = [first_message]
    if boundary:
        result_messages.append(boundary)
    result_messages.extend(kept_messages)

    tokens_freed = snip_tokens_freed(
        messages, result_messages, ""
    )

    return SnipResult(
        messages=result_messages,
        tokens_freed=tokens_freed,
        boundary_message=boundary
    )


def auto_compact(
    messages: list[Any],
    system_prompt: str,
    context: Any = None,
    threshold: int = 80000
) -> AutoCompactResult:
    """
    Perform automatic context compaction when threshold is exceeded.

    AutoCompact keeps recent messages and summarizes or removes older ones
    to stay under the token threshold.

    Args:
        messages: List of messages to compact
        system_prompt: The system prompt
        context: Optional context for compaction decisions
        threshold: Token count threshold for triggering compaction

    Returns:
        AutoCompactResult with compacted messages and tokens freed
    """
    # Calculate current token count
    current_tokens = count_tokens(system_prompt)
    for msg in messages:
        content = extract_message_content(msg).get("content", "")
        current_tokens += count_tokens(content)

    if current_tokens <= threshold:
        return AutoCompactResult(
            messages=messages,
            tokens_freed=0,
            boundary_message=None
        )

    # Build messages list including system prompt
    all_content = [system_prompt]
    for msg in messages:
        content = extract_message_content(msg).get("content", "")
        all_content.append(content)

    # Strategy: find middle point to remove while keeping recent
    target_tokens = threshold // 2  # Target half of threshold

    # Work backwards from end, keeping messages until we hit target
    result_messages = []
    accumulated_tokens = count_tokens(system_prompt)

    for msg in reversed(messages):
        content = extract_message_content(msg).get("content", "")
        msg_tokens = count_tokens(content)

        if accumulated_tokens + msg_tokens <= target_tokens:
            result_messages.insert(0, msg)
            accumulated_tokens += msg_tokens
        else:
            # This message would exceed target - mark as boundary
            break

    # If we removed some messages, add boundary
    removed_count = len(messages) - len(result_messages)
    boundary = None

    if removed_count > 0:
        boundary_content = f"[{removed_count} older messages summarized]"
        boundary = type('obj', (object,), {
            "uuid": "auto-boundary-uuid",
            "type": "user",
            "is_meta": True,
            "is_compact_summary": True,
            "message": {"content": boundary_content}
        })()

    # Build final message list
    final_messages = []
    if boundary:
        final_messages.append(boundary)
    final_messages.extend(result_messages)

    tokens_freed = snip_tokens_freed(messages, final_messages, system_prompt)

    return AutoCompactResult(
        messages=final_messages,
        tokens_freed=tokens_freed,
        boundary_message=boundary
    )


def reactive_compact(
    messages: list[Any],
    error: str
) -> bool:
    """
    Determine if reactive compaction should be triggered based on error.

    ReactiveCompact is triggered by 413 errors (context length exceeded)
    or similar capacity errors.

    Args:
        messages: Current message list
        error: Error message or code

    Returns:
        True if compaction should be triggered
    """
    error_str = str(error).lower()

    # 413 is the HTTP status code for "Payload Too Large"
    # This commonly indicates context length exceeded
    trigger_codes = ["413", "context_length", "too_long", "max_tokens", "limit"]

    for code in trigger_codes:
        if code in error_str:
            return True

    return False


class SnipCompact:
    """
    Snip compaction strategy - removes middle messages to save tokens.

    Maintains first message (system) and recent messages, removes middle
    section with a boundary marker.
    """

    def __init__(self, threshold: int = 50000):
        """
        Initialize SnipCompact.

        Args:
            threshold: Token count that triggers snip compaction
        """
        self._threshold = threshold

    @property
    def threshold(self) -> int:
        """Get the threshold."""
        return self._threshold

    def compact(self, messages: list[Any]) -> SnipResult:
        """
        Apply snip compaction to messages.

        Args:
            messages: Messages to compact

        Returns:
            SnipResult with compacted messages
        """
        return snip_compact_if_needed(messages, self._threshold)

    def should_compact(self, messages: list[Any]) -> bool:
        """
        Check if compaction is needed.

        Args:
            messages: Messages to check

        Returns:
            True if token count exceeds threshold
        """
        total_tokens = sum(
            count_tokens(extract_message_content(m).get("content", ""))
            for m in messages
        )
        return total_tokens > self._threshold


class AutoCompactStrategy:
    """
    Auto compaction strategy - automatic threshold-based compression.

    Automatically compacts when token count exceeds threshold, keeping
    recent messages and summarizing/removing older ones.
    """

    def __init__(self, threshold: int = 80000):
        """
        Initialize AutoCompactStrategy.

        Args:
            threshold: Token count that triggers auto compaction
        """
        self._threshold = threshold

    @property
    def threshold(self) -> int:
        """Get the threshold."""
        return self._threshold

    def compact(
        self,
        messages: list[Any],
        system_prompt: str,
        context: Any = None
    ) -> AutoCompactResult:
        """
        Apply auto compaction to messages.

        Args:
            messages: Messages to compact
            system_prompt: System prompt to include in token count
            context: Optional context for compaction decisions

        Returns:
            AutoCompactResult with compacted messages
        """
        return auto_compact(messages, system_prompt, context, self._threshold)

    def should_compact(self, messages: list[Any], system_prompt: str) -> bool:
        """
        Check if compaction is needed.

        Args:
            messages: Messages to check
            system_prompt: System prompt to include in token count

        Returns:
            True if token count exceeds threshold
        """
        total_tokens = count_tokens(system_prompt)
        for msg in messages:
            content = extract_message_content(msg).get("content", "")
            total_tokens += count_tokens(content)
        return total_tokens > self._threshold


class ReactiveCompact:
    """
    Reactive compaction strategy - triggered by errors.

    Activated when a 413 or similar error indicates context is too long.
    """

    def __init__(self):
        """Initialize ReactiveCompact."""
        pass

    def should_compact(self, error: str) -> bool:
        """
        Check if compaction should be triggered by error.

        Args:
            error: Error message or code

        Returns:
            True if error indicates compaction needed
        """
        return reactive_compact(messages=[], error=error)

    def compact(
        self,
        messages: list[Any],
        system_prompt: str,
        context: Any = None
    ) -> AutoCompactResult:
        """
        Perform aggressive compaction after error.

        More aggressive than AutoCompact since we know context is too long.

        Args:
            messages: Messages to compact
            system_prompt: System prompt
            context: Optional context

        Returns:
            AutoCompactResult with aggressively compacted messages
        """
        # Use lower threshold since we got an error
        return auto_compact(messages, system_prompt, context, threshold=60000)
