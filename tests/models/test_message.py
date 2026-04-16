import pytest
from dataclasses import is_dataclass
from claude_core.models.message import (
    Message,
    UserMessage,
    AssistantMessage,
    SystemMessage,
    AttachmentMessage,
    ProgressMessage,
    ToolResult,
    MessageType,
)

def test_message_is_dataclass():
    assert is_dataclass(Message)
    assert is_dataclass(UserMessage)
    assert is_dataclass(AssistantMessage)

def test_user_message_creation():
    msg = UserMessage(uuid="test-uuid", message={"content": "Hello"})
    assert msg.type == "user"
    assert msg.uuid == "test-uuid"

def test_assistant_message_creation():
    msg = AssistantMessage(
        uuid="test-uuid",
        message={"content": [{"type": "text", "text": "Hi"}]}
    )
    assert msg.type == "assistant"

def test_tool_result_creation():
    result = ToolResult(
        tool_use_id="tool-123",
        content="file content here",
        is_error=False
    )
    assert result.tool_use_id == "tool-123"
    assert result.is_error is False