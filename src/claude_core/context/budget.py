"""Token budget management."""

from dataclasses import dataclass, field
from typing import Optional

@dataclass
class TokenBudget:
    """
    Token budget tracker for API usage.

    Tracks prompt/completion token usage and calculates remaining budget.
    """
    max_tokens: int
    used_tokens: int = 0

    def add_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Add token usage from an API response."""
        self.used_tokens += prompt_tokens + completion_tokens

    @property
    def remaining_tokens(self) -> int:
        """Get remaining tokens in budget."""
        return max(0, self.max_tokens - self.used_tokens)

    @property
    def usage_percentage(self) -> float:
        """Get usage as a percentage of max."""
        if self.max_tokens == 0:
            return 0.0
        return (self.used_tokens / self.max_tokens) * 100

    def is_exhausted(self) -> bool:
        """Check if budget is exhausted."""
        return self.remaining_tokens <= 0

    def reset(self) -> None:
        """Reset the budget."""
        self.used_tokens = 0