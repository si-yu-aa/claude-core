"""Message type definitions."""

from dataclasses import dataclass, field
from typing import Literal, Any, Optional

MessageType = Literal[
    "user", "assistant", "system", "attachment", "progress", "grouped_tool_use"
]

@dataclass
class Message:
    """Base message type."""
    uuid: str
    type: MessageType = "user"
    is_meta: bool = False
    is_compact_summary: bool = False
    tool_use_result: Any = None
    is_visible_in_transcript_only: bool = False
    message: dict = field(default_factory=dict)

@dataclass
class UserMessage(Message):
    """User message."""
    type: Literal["user"] = "user"
    image_paste_ids: Optional[list[int]] = None

@dataclass
class AssistantMessage(Message):
    """Assistant message."""
    type: Literal["assistant"] = "assistant"

@dataclass
class SystemMessage(Message):
    """System message."""
    type: Literal["system"] = "system"

@dataclass
class AttachmentMessage(Message):
    """Attachment message."""
    type: Literal["attachment"] = "attachment"
    attachment: dict = field(default_factory=dict)

@dataclass
class ProgressMessage(Message):
    """Progress message for tool execution progress."""
    type: Literal["progress"] = "progress"
    data: Any = None

@dataclass
class ToolResult:
    """Tool execution result."""
    tool_use_id: str
    content: str | list[dict]
    is_error: bool = False

def create_user_message(
    content: str | list[dict],
    uuid: Optional[str] = None,
    tool_use_result: Any = None,
    source_tool_assistant_uuid: Optional[str] = None,
) -> UserMessage:
    """Helper to create a user message with tool result."""
    from claude_core.utils.uuid import generate_uuid

    msg_content = content if isinstance(content, list) else [{"type": "text", "text": content}]
    message_dict = {
        "role": "user",
        "content": msg_content,
    }
    if source_tool_assistant_uuid:
        message_dict["sourceToolAssistantUUID"] = source_tool_assistant_uuid

    return UserMessage(
        uuid=uuid or generate_uuid(),
        message=message_dict,
        tool_use_result=tool_use_result,
    )

def create_progress_message(
    tool_use_id: str,
    data: dict,
    parent_tool_use_id: Optional[str] = None,
) -> ProgressMessage:
    """Helper to create a progress message."""
    from claude_core.utils.uuid import generate_uuid

    return ProgressMessage(
        uuid=generate_uuid(),
        message={},
        data={
            "type": "tool_progress",
            "toolUseID": tool_use_id,
            "parentToolUseID": parent_tool_use_id,
            "data": data,
        }
    )
