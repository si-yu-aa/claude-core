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
    from claude_core.models.message import UserMessage, AssistantMessage, create_user_message
    from claude_core.tools.streaming_executor import StreamingToolExecutor

    state = QueryState(
        messages=params.messages,
        tool_use_context=params.tool_use_context,
        max_output_tokens_override=params.max_output_tokens_override,
    )

    # Create LLM client if not provided in context
    client = None
    if params.tool_use_context and hasattr(params.tool_use_context, '_client'):
        client = params.tool_use_context._client
    else:
        # Create a default client - caller should set this up properly
        from claude_core.api.client import LLMClient
        # Default to OpenAI-compatible endpoint
        client = None  # Will be created on first iteration if needed

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

        # Prepare messages for API
        api_messages = []
        for msg in state.messages:
            if isinstance(msg, UserMessage):
                content = msg.message.get("content", "")
                if isinstance(content, list):
                    api_messages.append({"role": "user", "content": content})
                else:
                    api_messages.append({"role": "user", "content": str(content)})
            elif isinstance(msg, AssistantMessage):
                content = msg.message.get("content", [])
                if isinstance(content, list):
                    api_messages.append({"role": "assistant", "content": content})
                else:
                    api_messages.append({"role": "assistant", "content": str(content)})

        # Get tools if available
        tools = None
        if state.tool_use_context and state.tool_use_context.options.tools:
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

        # Create client if needed
        if client is None:
            # Try to get from context or use defaults
            if state.tool_use_context and hasattr(state.tool_use_context, '_client'):
                client = state.tool_use_context._client
            else:
                # Yield error and stop if no client available
                yield {
                    "type": "error",
                    "error": "No LLM client configured. Set up client before calling query()."
                }
                yield Stop(reason="error")
                return

        # Collect content from streaming response
        full_content = ""
        tool_use_blocks = []
        stop_reason = None

        # Stream response from model
        try:
            async for event in call_model(
                client,
                api_messages,
                system_content,
                tools=tools,
                max_tokens=params.max_output_tokens_override or DEFAULT_MAX_OUTPUT_TOKENS,
                abort_controller=state.tool_use_context.abort_controller if state.tool_use_context else None,
            ):
                if event.type == "content_block_delta":
                    content = event.delta.get("content", "")
                    if content:
                        full_content += content
                        yield {
                            "type": "content",
                            "content": content,
                        }
                elif event.type == "tool_use":
                    tool_use_blocks.append({
                        "id": event.tool_use_id,
                        "name": event.name,
                        "input": event.input,
                    })
                elif event.type == "message_stop":
                    stop_reason = "stop"

        except Exception as e:
            error_message = str(e)
            is_prompt_too_long = "prompt" in error_message.lower() and "too" in error_message.lower()
            is_max_output = "output" in error_message.lower() and "token" in error_message.lower()

            if is_prompt_too_long:
                yield {
                    "type": "error",
                    "error": "Prompt too long. Consider using compression or reducing context.",
                    "error_code": "prompt_too_long",
                }
                yield Stop(reason="prompt_too_long")
                return
            elif is_max_output:
                yield {
                    "type": "error",
                    "error": "Max output tokens exceeded.",
                    "error_code": "max_output_tokens",
                }
                yield Stop(reason="max_output_tokens")
                return
            else:
                yield {
                    "type": "error",
                    "error": error_message,
                }
                yield Stop(reason="error")
                return

        # If we got content, create an assistant message
        if full_content:
            assistant_msg = {
                "type": "assistant",
                "content": full_content,
            }
            yield assistant_msg
            state.messages.append(type('obj', (object,), {
                "type": "assistant",
                "uuid": generate_uuid(),
                "message": assistant_msg,
            })())

        # If there are tool use blocks, execute them
        if tool_use_blocks:
            # Create assistant message with tool use blocks
            assistant_message = type('obj', (object,), {
                "uuid": generate_uuid(),
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": tb["id"],
                            "name": tb["name"],
                            "input": tb["input"],
                        }
                        for tb in tool_use_blocks
                    ]
                },
            })()

            # Yield tool use events
            for tb in tool_use_blocks:
                yield {
                    "type": "tool_use",
                    "tool_use_id": tb["id"],
                    "name": tb["name"],
                    "input": tb["input"],
                }

            # Execute tools using StreamingToolExecutor
            if state.tool_use_context:
                executor = StreamingToolExecutor(
                    tool_definitions=state.tool_use_context.options.tools,
                    can_use_tool=params.can_use_tool,
                    tool_use_context=state.tool_use_context,
                )

                # Add all tool blocks
                for tb in tool_use_blocks:
                    block = type('obj', (object,), {
                        "id": tb["id"],
                        "name": tb["name"],
                        "input": tb["input"],
                        "type": "tool_use",
                    })()
                    executor.add_tool(block, assistant_message)

                # Get results
                async for update in executor.get_remaining_results():
                    if update.message:
                        # Yield tool result message
                        yield {
                            "type": "tool_result",
                            "tool_use_id": update.message.message.get("tool_use_result", {}).get("tool_use_id", "") if hasattr(update.message, 'message') else "",
                            "content": update.message.tool_use_result if hasattr(update.message, 'tool_use_result') else str(update.message),
                        }
                        state.messages.append(update.message)

                # Update context with any modifiers
                state.tool_use_context = executor.get_updated_context()

        # Check stop reason
        if stop_reason == "stop" and not tool_use_blocks:
            # Normal completion - no more tools to execute
            yield Stop(reason="complete")
            return

        # Increment turn count and continue
        state.turn_count += 1

        # Continue the loop for more turns if tools were executed
        if tool_use_blocks:
            yield Continue()
        else:
            # No tools and no content - something went wrong
            yield Stop(reason="complete")
            return