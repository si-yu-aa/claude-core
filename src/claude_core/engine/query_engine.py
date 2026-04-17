"""QueryEngine - high-level orchestrator for LLM queries."""

from __future__ import annotations

from typing import AsyncGenerator, Any, Optional

from claude_core.engine.config import QueryEngineConfig
from claude_core.engine.query_loop import query
from claude_core.engine.types import QueryParams
from claude_core.models.message import create_user_message
from claude_core.utils.abort import AbortController, create_child_abort_controller
from claude_core.api.client import LLMClient

EMPTY_USAGE = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


class QueryEngine:
    """
    High-level query engine managing conversation lifecycle and session state.

    Responsibilities:
    - Manage session message history
    - Process user input
    - Track API usage
    - Handle permissions and denials
    """

    def __init__(self, config: QueryEngineConfig):
        self._config = config
        self._messages: list[Any] = []
        self._abort_controller = AbortController()
        self._permission_denials: list = []
        self._total_usage: dict = dict(EMPTY_USAGE)
        self._client: Optional[LLMClient] = None

    @property
    def config(self) -> QueryEngineConfig:
        """Get the engine configuration."""
        return self._config

    @property
    def messages(self) -> list[Any]:
        """Get all messages in the conversation."""
        return self._messages

    async def _get_client(self) -> LLMClient:
        """Get or create the LLM client."""
        if self._client is None:
            self._client = LLMClient(
                base_url=self._config.base_url,
                api_key=self._config.api_key,
                model=self._config.model,
                timeout=self._config.timeout,
            )
        return self._client

    async def submit_message(
        self,
        content: str,
    ) -> AsyncGenerator[dict, None]:
        """
        Submit a user message and return an event stream.

        Args:
            content: The user's message content

        Yields:
            Stream events as they arrive
        """
        # Create user message
        user_msg = create_user_message(content=content)
        self._messages.append(user_msg)

        # Ensure client is initialized
        await self._get_client()

        # Prepare tools if available
        tools = None
        if hasattr(self, '_tools') and self._tools:
            tools = []
            for tool in self._tools:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema,
                    }
                })

        # Build tool_use_context with tools if tools are available
        tool_use_context = None
        if hasattr(self, '_tool_use_context') and self._tool_use_context:
            tool_use_context = self._tool_use_context
            if tools:
                tool_use_context.options.tools = tools
            tool_use_context.abort_controller = create_child_abort_controller(
                self._abort_controller
            )
        elif tools:
            # Create minimal context if no context but tools provided
            from claude_core.models.tool import ToolUseContext, ToolUseContextOptions
            tool_use_context = ToolUseContext(
                options=ToolUseContextOptions(tools=tools),
                abort_controller=create_child_abort_controller(self._abort_controller),
            )

        # Create query params
        params = QueryParams(
            messages=self._messages,
            system_prompt=self._system_prompt if hasattr(self, '_system_prompt') else "You are a helpful assistant.",
            user_context={},
            system_context={},
            can_use_tool=self._can_use_tool if hasattr(self, '_can_use_tool') else lambda *args: True,
            tool_use_context=tool_use_context,
            max_turns=self._config.max_turns,
            max_output_tokens_override=self._config.max_output_tokens,
            fallback_model=None,
            query_source="sdk",
        )

        try:
            async for event in query(params):
                if isinstance(event, dict):
                    if event.get("type") == "message" and event.get("message"):
                        self._messages.append(event["message"])
                    yield event
                else:
                    yield event

        except Exception as e:
            yield {"type": "error", "error": str(e)}

    async def ask(self, prompt: str, **kwargs) -> str:
        """
        Simple blocking ask interface.

        Args:
            prompt: The question/prompt to ask
            **kwargs: Additional arguments for submit_message

        Returns:
            The model's response as a string
        """
        results = []
        async for event in self.submit_message(prompt, **kwargs):
            if isinstance(event, dict):
                if event.get("type") == "content":
                    results.append(event.get("content", ""))
            elif hasattr(event, 'type'):
                if event.type == "content_block_delta":
                    results.append(event.delta.get("content", ""))

        return "".join(results)

    def set_system_prompt(self, prompt: str) -> None:
        """Set the system prompt."""
        self._system_prompt = prompt

    def set_tools(self, tools: list) -> None:
        """Set the available tools."""
        self._tools = tools

    def set_can_use_tool(self, can_use_tool: callable) -> None:
        """Set the can_use_tool callback."""
        self._can_use_tool = can_use_tool

    def set_tool_use_context(self, context) -> None:
        """Set the tool use context."""
        self._tool_use_context = context

    def stop(self) -> None:
        """Stop the current query."""
        self._abort_controller.abort("user_stop")
