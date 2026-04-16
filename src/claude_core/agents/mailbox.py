"""Mailbox for agent message passing."""

from __future__ import annotations

from typing import Any, Optional
from dataclasses import dataclass, field
from collections import deque

@dataclass
class MailboxMessage:
    """A message in the mailbox."""
    sender_id: str
    content: Any
    timestamp: float = 0.0

class Mailbox:
    """
    Mailbox for passing messages between agents.

    Provides a simple message queue with send/receive operations.
    """

    def __init__(self):
        self._messages: deque[MailboxMessage] = deque()
        self._subscribers: dict[str, Any] = {}

    def send(self, sender_id: str, content: Any) -> None:
        """Send a message to the mailbox."""
        from time import time
        msg = MailboxMessage(
            sender_id=sender_id,
            content=content,
            timestamp=time(),
        )
        self._messages.append(msg)

    def receive(self, recipient_id: str) -> MailboxMessage | None:
        """Receive a message for a specific recipient."""
        while self._messages:
            msg = self._messages.popleft()
            # Simple implementation: any message is for anyone
            return msg
        return None

    def peek(self) -> MailboxMessage | None:
        """Peek at the next message without removing it."""
        if self._messages:
            return self._messages[0]
        return None

    def clear(self) -> None:
        """Clear all messages."""
        self._messages.clear()

    @property
    def is_empty(self) -> bool:
        """Check if mailbox is empty."""
        return len(self._messages) == 0

    @property
    def message_count(self) -> int:
        """Get the number of messages."""
        return len(self._messages)