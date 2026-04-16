"""Context Manager for token budget and context window management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from claude_core.context.budget import TokenBudget
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

    @property
    def budget(self) -> TokenBudget:
        """Get the token budget."""
        return self._budget

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

        return False

    async def compact(
        self,
        messages: list[Any],
        system_prompt: str,
        context: Any = None,
    ) -> CompactionResult:
        """
        Perform context compaction.

        Uses a simple strategy: keep recent messages and summarize older ones.

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

        # Simple compaction: keep recent messages, summarize older
        # Keep last N messages that fit in half the budget
        half_budget = self._max_tokens // 2
        recent_messages = []
        older_messages = []

        current_count = count_tokens(system_prompt)
        for msg in reversed(messages):
            msg_tokens = count_tokens(str(msg.message.get("content", "")) if hasattr(msg, "message") else str(msg))
            if current_count + msg_tokens < half_budget:
                recent_messages.insert(0, msg)
                current_count += msg_tokens
            else:
                older_messages.insert(0, msg)

        # Create summary of older messages
        summary_content = f"[Previous {len(older_messages)} messages summarized]"
        summary_message = type('obj', (object,), {
            "type": "user",
            "uuid": "summary-uuid",
            "message": {"content": summary_content}
        })()

        post_compact_count = count_tokens(system_prompt) + count_tokens(summary_content) + current_count

        return CompactionResult(
            summary_messages=[summary_message] + recent_messages,
            attachments=[],
            hook_results=[],
            pre_compact_token_count=pre_compact_count,
            post_compact_token_count=post_compact_count,
            true_post_compact_token_count=post_compact_count,
            compaction_usage=None,
        )

    def update_budget(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Update token budget with new usage."""
        self._budget.add_usage(prompt_tokens, completion_tokens)

    def reset_budget(self) -> None:
        """Reset the token budget."""
        self._budget.reset()