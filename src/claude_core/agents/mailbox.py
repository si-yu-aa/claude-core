"""Mailbox for agent message passing."""

from __future__ import annotations

from typing import Any, Optional
from dataclasses import dataclass, field
from collections import deque

@dataclass
class MailboxMessage:
    """A message in the mailbox."""
    sender_id: str
    recipient_id: str
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

    def send(self, sender_id: str, recipient_id: str, content: Any | None = None) -> None:
        """Send a message to the mailbox."""
        from time import time
        if content is None:
            # Backwards-compatible form: send(sender_id, content)
            content = recipient_id
            recipient_id = "*"
        msg = MailboxMessage(
            sender_id=sender_id,
            recipient_id=recipient_id,
            content=content,
            timestamp=time(),
        )
        self._messages.append(msg)

    def receive(self, recipient_id: str) -> MailboxMessage | None:
        """Receive a message for a specific recipient."""
        for _ in range(len(self._messages)):
            msg = self._messages.popleft()
            if msg.recipient_id in {"*", recipient_id}:
                return msg
            self._messages.append(msg)
        return None

    def pending_count(self, recipient_id: str) -> int:
        """Count messages pending for a recipient."""
        return sum(1 for msg in self._messages if msg.recipient_id in {"*", recipient_id})

    def list_messages(self, recipient_id: str | None = None) -> list[MailboxMessage]:
        """Return mailbox messages, optionally filtered by recipient."""
        messages = list(self._messages)
        if recipient_id is None:
            return messages
        return [msg for msg in messages if msg.recipient_id in {"*", recipient_id}]

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
