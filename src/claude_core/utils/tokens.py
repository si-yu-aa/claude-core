"""Token counting utilities."""

def count_tokens(text: str) -> int:
    """
    Estimate token count for a given text.

    Uses a simple approximation: ~4 characters per token for English text.
    """
    return len(text) // 4

def count_tokens_for_messages(messages: list[dict]) -> int:
    """Count tokens for a list of messages."""
    total = 0
    for msg in messages:
        if isinstance(msg, dict):
            content = msg.get("content", "")
            if isinstance(content, str):
                total += count_tokens(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        total += count_tokens(block.get("text", ""))
                    elif isinstance(block, str):
                        total += count_tokens(block)
    return total