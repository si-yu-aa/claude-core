"""Context Manager for token budget and context window management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from claude_core.context.budget import TokenBudget
from claude_core.context.compression import (
    SnipCompact,
    AutoCompactStrategy,
    ReactiveCompact,
    snip_compact_if_needed,
    auto_compact,
    reactive_compact,
    SnipResult,
    AutoCompactResult,
)
from claude_core.utils.tokens import count_tokens, count_tokens_for_messages

@dataclass
class CompactionResult:
    """Result of context compaction."""
    summary_messages: list[Any]
    attachments: list[Any]
    hook_results: list[Any]
    pre_compact_token_count: int
    post_compact_token_count: int
    true_post_compact_token_count: int
    compaction_usage: dict | None

class ContextManager:
    """
    Context manager for token budget and context window management.

    Compression strategies:
    1. AutoCompact - automatic compression (threshold triggered)
    2. Microcompact - micro compression (edited cached messages)
    3. Snip - history trimming (remove middle messages)
    4. Collapse - context collapse (preserve key points)
    5. Reactive Compact - reactive compression (after 413 error)
    """

    def __init__(self, max_tokens: int, model: str = "gpt-4o"):
        self._max_tokens = max_tokens
        self._model = model
        self._budget = TokenBudget(max_tokens=max_tokens)
        self._compact_threshold = int(max_tokens * 0.8)  # 80% threshold

        # Initialize compression strategies
        self._snip_compact = SnipCompact(threshold=50000)
        self._auto_compact = AutoCompactStrategy(threshold=80000)
        self._reactive_compact = ReactiveCompact()

    @property
    def budget(self) -> TokenBudget:
        """Get the token budget."""
        return self._budget

    @property
    def snip_compact(self) -> SnipCompact:
        """Get the snip compact strategy."""
        return self._snip_compact

    @property
    def auto_compact(self) -> AutoCompactStrategy:
        """Get the auto compact strategy."""
        return self._auto_compact

    @property
    def reactive_compact_strategy(self) -> ReactiveCompact:
        """Get the reactive compact strategy."""
        return self._reactive_compact

    async def should_compact(
        self, messages: list[Any], token_count: int
    ) -> bool:
        """
        Determine if compaction is needed.

        Args:
            messages: List of messages in context
            token_count: Current token count

        Returns:
            True if compaction should be performed
        """
        # Check if over threshold
        if token_count >= self._compact_threshold:
            return True

        # Check if budget is exhausted
        if self._budget.is_exhausted():
            return True

        # Check using snip compact strategy
        if self._snip_compact.should_compact(messages):
            return True

        return False

    async def compact(
        self,
        messages: list[Any],
        system_prompt: str,
        context: Any = None,
    ) -> CompactionResult:
        """
        Perform context compaction using AutoCompact strategy.

        Args:
            messages: List of messages to compact
            system_prompt: The system prompt
            context: Optional tool use context

        Returns:
            CompactionResult with summary and updated messages
        """
        pre_compact_count = count_tokens_for_messages([
            {"content": system_prompt},
            *[{"content": str(m.message.get("content", "")) if hasattr(m, "message") else str(m)} for m in messages]
        ])

        # Use AutoCompact strategy
        result: AutoCompactResult = self._auto_compact.compact(
            messages, system_prompt, context
        )

        post_compact_count = pre_compact_count - result.tokens_freed

        return CompactionResult(
            summary_messages=result.messages,
            attachments=[],
            hook_results=[],
            pre_compact_token_count=pre_compact_count,
            post_compact_token_count=post_compact_count,
            true_post_compact_token_count=post_compact_count,
            compaction_usage={"tokens_freed": result.tokens_freed},
        )

    async def snip_compact(
        self,
        messages: list[Any],
    ) -> SnipResult:
        """
        Perform snip compaction - removes middle messages.

        Args:
            messages: List of messages to compact

        Returns:
            SnipResult with compacted messages
        """
        return self._snip_compact.compact(messages)

    async def reactive_compact(
        self,
        messages: list[Any],
        system_prompt: str,
        error: str,
        context: Any = None,
    ) -> tuple[bool, CompactionResult]:
        """
        Perform reactive compaction after 413 error.

        Args:
            messages: List of messages to compact
            system_prompt: The system prompt
            error: The error that triggered compaction
            context: Optional context

        Returns:
            Tuple of (should_compact, CompactionResult)
        """
        should_compact = reactive_compact(messages, error)
        if not should_compact:
            return False, None

        # Use reactive compact strategy for more aggressive compression
        result: AutoCompactResult = self._reactive_compact.compact(
            messages, system_prompt, context
        )

        pre_compact_count = count_tokens_for_messages([
            {"content": system_prompt},
            *[{"content": str(m.message.get("content", "")) if hasattr(m, "message") else str(m)} for m in messages]
        ])

        post_compact_count = pre_compact_count - result.tokens_freed

        return True, CompactionResult(
            summary_messages=result.messages,
            attachments=[],
            hook_results=[],
            pre_compact_token_count=pre_compact_count,
            post_compact_token_count=post_compact_count,
            true_post_compact_token_count=post_compact_count,
            compaction_usage={"tokens_freed": result.tokens_freed, "trigger": "reactive"},
        )

    def update_budget(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Update token budget with new usage."""
        self._budget.add_usage(prompt_tokens, completion_tokens)

    def reset_budget(self) -> None:
        """Reset the token budget."""
        self._budget.reset()


# Model context window sizes (in tokens)
_MODEL_CONTEXT_WINDOWS = {
    "gpt-4o": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4": 8192,
    "gpt-4-32k": 32768,
    "gpt-3.5-turbo": 16385,
    "gpt-3.5-turbo-16k": 16385,
    "claude-3-opus": 200000,
    "claude-3-sonnet": 200000,
    "claude-3-haiku": 200000,
    "claude-3.5-opus": 200000,
    "claude-3.5-sonnet": 200000,
    "claude-3.5-haiku": 200000,
}

# Models with 1M context window
_MODELS_WITH_1M_CONTEXT = {
    "claude-3.5-sonnet-20240620": True,
    "claude-3.5-sonnet-20241022": True,
}


def get_model_context_window(model: str) -> int:
    """Get the context window size for a model.

    Args:
        model: The model name

    Returns:
        The context window size in tokens, defaults to 128000
    """
    return _MODEL_CONTEXT_WINDOWS.get(model, 128000)


def has_1m_context(model: str) -> bool:
    """Check if a model has a 1M token context window.

    Args:
        model: The model name

    Returns:
        True if the model has a 1M context window
    """
    return model in _MODELS_WITH_1M_CONTEXT