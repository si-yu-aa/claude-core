"""Query Engine configuration."""

from dataclasses import dataclass
from typing import Optional

@dataclass
class QueryEngineConfig:
    """Configuration for QueryEngine."""
    api_key: str
    model: str = "gpt-4o"
    base_url: str = "https://api.openai.com/v1"
    max_turns: Optional[int] = None
    max_output_tokens: Optional[int] = None
    temperature: float = 0.7
    timeout: float = 120.0

    # Context settings
    max_context_tokens: int = 100000
    compact_threshold_tokens: int = 80000

    # Tool settings
    tool_timeout: int = 60

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0