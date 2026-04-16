"""API type definitions."""

from dataclasses import dataclass
from typing import Literal, Any, Optional

@dataclass
class MessageParam:
    """A message parameter for the API."""
    role: Literal["system", "user", "assistant"]
    content: str | list[dict]
    name: Optional[str] = None

@dataclass
class ToolParam:
    """A tool parameter for the API."""
    function: "FunctionDefinition"
    type: Literal["function"] = "function"

@dataclass
class FunctionDefinition:
    """Function definition for a tool."""
    name: str
    description: str
    parameters: dict[str, Any]

@dataclass
class ChatCompletionChoice:
    """A choice in a chat completion response."""
    index: int
    message: dict
    finish_reason: str

@dataclass
class Usage:
    """Token usage information."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

@dataclass
class ChatCompletion:
    """A non-streaming chat completion response."""
    id: str
    model: str
    choices: list[ChatCompletionChoice]
    usage: Usage
    created: int