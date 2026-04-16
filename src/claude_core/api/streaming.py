"""Streaming response handling."""

from dataclasses import dataclass, field
from typing import AsyncGenerator, Any, Optional, Literal
import json

@dataclass
class StreamEvent:
    """Base class for stream events."""
    type: str

@dataclass
class ContentBlockDeltaEvent(StreamEvent):
    """A content block delta event."""
    type: Literal["content_block_delta"] = "content_block_delta"
    index: int = 0
    delta: dict = field(default_factory=dict)

@dataclass
class MessageDeltaEvent(StreamEvent):
    """A message delta event."""
    type: Literal["message_delta"] = "message_delta"
    delta: dict = field(default_factory=dict)
    usage: Optional[dict] = None

@dataclass
class MessageStopEvent(StreamEvent):
    """A message stop event."""
    type: Literal["message_stop"] = "message_stop"

def parse_sse_line(line: str) -> Optional[dict]:
    """Parse a Server-Sent Events line."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("data: "):
        return json.loads(line[6:])
    return None

async def parse_stream_response(response: "httpx.Response") -> AsyncGenerator[StreamEvent, None]:
    """Parse a streaming HTTP response into events."""
    async for line in response.aiter_lines():
        data = parse_sse_line(line)
        if not data:
            continue

        if data.get("choices"):
            for choice in data["choices"]:
                delta = choice.get("delta", {})
                if delta.get("content"):
                    yield ContentBlockDeltaEvent(
                        index=choice.get("index", 0),
                        delta={"content": delta["content"]}
                    )
                if choice.get("finish_reason"):
                    yield MessageStopEvent()