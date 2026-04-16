import pytest
import asyncio
from claude_core.tools.streaming_executor import (
    StreamingToolExecutor,
    ToolStatus,
)
from claude_core.tools.base import Tool, ToolResult, build_tool
from claude_core.models.tool import ToolUseContext, ToolUseContextOptions, ToolUseBlock
from claude_core.utils.abort import AbortController

@pytest.fixture
def mock_tool():
    def call(args, context, can_use_tool, on_progress=None):
        return ToolResult(
            tool_use_id="test-id",
            content=f"processed: {args.get('input', '')}"
        )

    return build_tool({
        "name": "MockTool",
        "description": "A mock tool for testing",
        "input_schema": {"type": "object", "properties": {"input": {"type": "string"}}},
        "call": call,
        "is_concurrency_safe": lambda args: True,
    })

@pytest.fixture
def tool_use_context():
    return ToolUseContext(
        options=ToolUseContextOptions(
            tools=[],
            debug=False,
            main_loop_model="gpt-4o",
        ),
        abort_controller=AbortController(),
    )

def create_tool_use_block(name: str, tool_id: str = "test-id", input_data: dict = None) -> ToolUseBlock:
    return ToolUseBlock(
        id=tool_id,
        name=name,
        input=input_data or {"input": "test"}
    )

@pytest.mark.asyncio
async def test_streaming_executor_discard(mock_tool, tool_use_context):
    executor = StreamingToolExecutor(
        tool_definitions=[mock_tool],
        can_use_tool=lambda *args: True,
        tool_use_context=tool_use_context,
    )

    executor.discard()
    assert executor._discarded is True

    block = create_tool_use_block("MockTool")
    assistant_msg = type("obj", (object,), {"uuid": "assist-1", "message": {"id": "msg-1", "content": []}})()
    executor.add_tool(block, assistant_msg)

    results = []
    async for update in executor.get_remaining_results():
        results.append(update)

    # Discarded executor should yield no results
    assert len(results) == 0