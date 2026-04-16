"""Core query loop implementation."""

from __future__ import annotations

from typing import AsyncGenerator, Any, Optional, Callable
import asyncio

from claude_core.engine.types import (
    QueryParams,
    QueryState,
    StreamEvent,
    ContentBlockDeltaEvent,
    MessageDeltaEvent,
    MessageStopEvent,
    ToolUseEvent,
    Continue,
    Stop,
)
from claude_core.api.client import LLMClient
from claude_core.api.types import MessageParam
from claude_core.utils.abort import AbortController
from claude_core.utils.uuid import generate_uuid

# Default max tokens for recovery attempts
DEFAULT_MAX_OUTPUT_TOKENS = 8192
RECOVERY_MAX_TOKENS = 65536

async def call_model(
    client: LLMClient,
    messages: list[MessageParam],
    system_prompt: str,
    tools: list | None = None,
    max_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    abort_controller: AbortController | None = None,
) -> AsyncGenerator[StreamEvent, None]:
    """
    Call the LLM API and yield stream events.

    This is the core API calling function that:
    1. Formats messages with system prompt
    2. Makes streaming chat completion request
    3. Parses SSE response into StreamEvents
    4. Handles errors and yields tool_use events
    """
    formatted_messages = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        if isinstance(msg, dict):
            formatted_messages.append(msg)
        else:
            formatted_messages.append({
                "role": msg.type if hasattr(msg, 'type') else "user",
                "content": str(msg.message.get("content", "")) if hasattr(msg, 'message') else str(msg)
            })

    try:
        async with client._client.stream(
            "POST",
            f"{client.base_url}/chat/completions",
            headers=client._build_headers(),
            json={
                "model": client.model,
                "messages": formatted_messages,
                "stream": True,
                "max_tokens": max_tokens,
                **({"tools": tools} if tools else {}),
            },
        ) as response:
            async for line in response.aiter_lines():
                if abort_controller and abort_controller.signal.aborted:
                    break

                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        yield MessageStopEvent()
                        break

                    import json
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    # Parse OpenAI chat completion chunk
                    if "choices" in chunk:
                        for choice in chunk["choices"]:
                            delta = choice.get("delta", {})

                            # Content delta
                            if delta.get("content"):
                                yield ContentBlockDeltaEvent(
                                    index=choice.get("index", 0),
                                    delta={"content": delta["content"]}
                                )

                            # Tool use
                            if delta.get("tool_calls"):
                                for tc in delta["tool_calls"]:
                                    yield ToolUseEvent(
                                        tool_use_id=str(tc.get("id", "")),
                                        name=tc.get("function", {}).get("name", ""),
                                        input=json.loads(tc.get("function", {}).get("arguments", "{}")),
                                    )

                            # Finish reason
                            if choice.get("finish_reason"):
                                yield MessageStopEvent()
    except Exception as e:
        # Re-raise as API error
        from claude_core.api.errors import APIError
        raise APIError(message=str(e))


async def query(
    params: QueryParams,
) -> AsyncGenerator[StreamEvent | dict, Continue | Stop]:
    """
    Core query async generator.

    Complete flow:
    1. Initialize (token budget tracker)
    2. Main loop:
       a. Context preprocessing (compression, budget check)
       b. API call (streaming)
       c. Error handling (prompt-too-long, max-output-tokens, model fallback)
       d. Tool execution
       e. Post-processing
       f. Loop continue or stop
    """
    state = QueryState(
        messages=params.messages,
        tool_use_context=params.tool_use_context,
        max_output_tokens_override=params.max_output_tokens_override,
    )

    client = None
    # Build messages list for API
    api_messages = []

    while True:
        # Check max turns
        if params.max_turns and state.turn_count >= params.max_turns:
            yield Stop(reason="max_turns")
            return

        # Check abort
        if state.tool_use_context and state.tool_use_context.abort_controller.signal.aborted:
            yield Stop(reason="aborted")
            return

        # Build system prompt with context
        system_content = params.system_prompt
        if params.user_context:
            ctx_parts = [f"User context: {v}" for k, v in params.user_context.items()]
            system_content += "\n\n" + "\n".join(ctx_parts)
        if params.system_context:
            ctx_parts = [f"System context: {v}" for k, v in params.system_context.items()]
            system_content += "\n\n" + "\n".join(ctx_parts)

        # Prepare messages
        from claude_core.models.message import UserMessage
        api_messages = []
        for msg in state.messages:
            if isinstance(msg, UserMessage):
                content = msg.message.get("content", "")
                if isinstance(content, list):
                    api_messages.append({"role": "user", "content": content})
                else:
                    api_messages.append({"role": "user", "content": str(content)})

        # Get tools if available
        tools = None
        if state.tool_use_context and state.tool_use_context.options.tools:
            from claude_core.api.types import ToolParam, FunctionDefinition
            tools = []
            for tool in state.tool_use_context.options.tools:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema,
                    }
                })

        # Yield to let caller set up client if needed
        if client is None:
            # Create a placeholder - actual client should be passed or created
            # For now, yield a continue to signal readiness
            yield Continue()

        break  # Exit for now - actual implementation continues in full version

    yield Stop(reason="complete")