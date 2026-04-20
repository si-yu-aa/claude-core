import pytest
import asyncio
from dataclasses import replace
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


@pytest.mark.asyncio
async def test_streaming_executor_waits_for_running_tool(tool_use_context):
    async def slow_call(args, context, can_use_tool, on_progress=None):
        await asyncio.sleep(0.05)
        return ToolResult(
            tool_use_id="slow-id",
            content="slow done",
        )

    slow_tool = build_tool({
        "name": "SlowTool",
        "description": "A slow mock tool for testing",
        "input_schema": {"type": "object", "properties": {}},
        "call": slow_call,
        "is_concurrency_safe": lambda args: True,
    })

    executor = StreamingToolExecutor(
        tool_definitions=[slow_tool],
        can_use_tool=lambda *args: True,
        tool_use_context=tool_use_context,
    )

    block = create_tool_use_block("SlowTool", tool_id="slow-id", input_data={})
    assistant_msg = type("obj", (object,), {"uuid": "assist-2", "message": {"id": "msg-2", "content": []}})()
    executor.add_tool(block, assistant_msg)

    results = []
    async for update in executor.get_remaining_results():
        results.append(update)

    assert len(results) == 1
    assert results[0].message.tool_use_result == "slow done"


@pytest.mark.asyncio
async def test_streaming_executor_uses_updated_permission_input(tool_use_context):
    captured_args = {}

    async def check_permissions(input_data, context):
        return build_tool_permission_result()

    def build_tool_permission_result():
        return __import__("claude_core.tools.base", fromlist=["PermissionResult"]).PermissionResult(
            behavior="allow",
            updated_input={"input": "sanitized"},
        )

    async def call(args, context, can_use_tool, on_progress=None):
        captured_args.update(args)
        return ToolResult(tool_use_id="perm-id", content=args["input"])

    tool = build_tool({
        "name": "PermissionedTool",
        "description": "Permissioned tool",
        "input_schema": {"type": "object", "properties": {"input": {"type": "string"}}},
        "check_permissions": check_permissions,
        "call": call,
        "is_concurrency_safe": lambda args: True,
    })

    executor = StreamingToolExecutor(
        tool_definitions=[tool],
        can_use_tool=lambda *args: True,
        tool_use_context=tool_use_context,
    )

    block = create_tool_use_block(
        "PermissionedTool",
        tool_id="perm-id",
        input_data={"input": "original"},
    )
    assistant_msg = type("obj", (object,), {"uuid": "assist-3", "message": {"id": "msg-3", "content": []}})()
    executor.add_tool(block, assistant_msg)

    results = []
    async for update in executor.get_remaining_results():
        results.append(update)

    assert captured_args == {"input": "sanitized"}
    assert len(results) == 1
    assert results[0].message.tool_use_result == "sanitized"


@pytest.mark.asyncio
async def test_streaming_executor_blocks_ask_permissions(tool_use_context):
    async def check_permissions(input_data, context):
        from claude_core.tools.base import PermissionResult
        return PermissionResult(behavior="ask", message="Needs confirmation")

    async def call(args, context, can_use_tool, on_progress=None):
        return ToolResult(tool_use_id="ask-id", content="should not run")

    tool = build_tool({
        "name": "AskTool",
        "description": "Tool requiring confirmation",
        "input_schema": {"type": "object", "properties": {}},
        "check_permissions": check_permissions,
        "call": call,
        "is_concurrency_safe": lambda args: True,
    })

    executor = StreamingToolExecutor(
        tool_definitions=[tool],
        can_use_tool=lambda *args: True,
        tool_use_context=tool_use_context,
    )

    block = create_tool_use_block("AskTool", tool_id="ask-id", input_data={})
    assistant_msg = type("obj", (object,), {"uuid": "assist-4", "message": {"id": "msg-4", "content": []}})()
    executor.add_tool(block, assistant_msg)

    results = []
    async for update in executor.get_remaining_results():
        results.append(update)

    assert len(results) == 1
    assert results[0].message.tool_use_result == "Needs confirmation"


@pytest.mark.asyncio
async def test_streaming_executor_matches_tool_alias(tool_use_context):
    async def alias_call(args, context, can_use_tool, on_progress=None):
        return ToolResult(
            tool_use_id="alias-id",
            content="alias matched",
        )

    alias_tool = build_tool({
        "name": "CanonicalTool",
        "description": "Tool with alias",
        "input_schema": {"type": "object", "properties": {}},
        "aliases": ["AliasTool"],
        "call": alias_call,
        "is_concurrency_safe": lambda args: True,
    })

    executor = StreamingToolExecutor(
        tool_definitions=[alias_tool],
        can_use_tool=lambda *args: True,
        tool_use_context=tool_use_context,
    )

    block = create_tool_use_block("AliasTool", tool_id="alias-id", input_data={})
    assistant_msg = type("obj", (object,), {"uuid": "assist-5", "message": {"id": "msg-5", "content": []}})()
    executor.add_tool(block, assistant_msg)

    results = []
    async for update in executor.get_remaining_results():
        results.append(update)

    assert len(results) == 1
    assert results[0].message.tool_use_result == "alias matched"


@pytest.mark.asyncio
async def test_streaming_executor_passes_child_abort_controller_and_propagates_parent_abort(
    tool_use_context,
):
    captured = {}
    release = asyncio.Event()

    async def call(args, context, can_use_tool, on_progress=None):
        captured["same_controller"] = context.abort_controller is tool_use_context.abort_controller
        captured["initially_aborted"] = context.abort_controller.signal.aborted
        await asyncio.sleep(0)
        tool_use_context.abort_controller.abort("user_stop")
        await asyncio.sleep(0)
        captured["child_aborted"] = context.abort_controller.signal.aborted
        captured["child_reason"] = context.abort_controller.signal.reason
        release.set()
        return ToolResult(tool_use_id="abort-id", content="done")

    tool = build_tool({
        "name": "AbortAwareTool",
        "description": "Tool that observes abort propagation",
        "input_schema": {"type": "object", "properties": {}},
        "call": call,
        "is_concurrency_safe": lambda args: True,
    })

    executor = StreamingToolExecutor(
        tool_definitions=[tool],
        can_use_tool=lambda *args: True,
        tool_use_context=tool_use_context,
    )

    block = create_tool_use_block("AbortAwareTool", tool_id="abort-id", input_data={})
    assistant_msg = type("obj", (object,), {"uuid": "assist-abort", "message": {"id": "msg-abort", "content": []}})()
    executor.add_tool(block, assistant_msg)

    results = []
    async for update in executor.get_remaining_results():
        results.append(update)

    await release.wait()

    assert len(results) == 1
    assert captured == {
        "same_controller": False,
        "initially_aborted": False,
        "child_aborted": True,
        "child_reason": "user_stop",
    }


@pytest.mark.asyncio
async def test_streaming_executor_does_not_reapply_context_modifier(tool_use_context):
    def modifier(context):
        context.messages = list(context.messages) + ["applied"]
        return context

    async def call(args, context, can_use_tool, on_progress=None):
        return ToolResult(
            tool_use_id="modifier-id",
            content="ok",
            context_modifier=modifier,
        )

    tool = build_tool({
        "name": "ModifierTool",
        "description": "Returns a context modifier",
        "input_schema": {"type": "object", "properties": {}},
        "call": call,
        "is_concurrency_safe": lambda args: False,
    })

    executor = StreamingToolExecutor(
        tool_definitions=[tool],
        can_use_tool=lambda *args: True,
        tool_use_context=replace(tool_use_context, messages=[]),
    )

    block = create_tool_use_block("ModifierTool", tool_id="modifier-id", input_data={})
    assistant_msg = type("obj", (object,), {"uuid": "assist-mod", "message": {"id": "msg-mod", "content": []}})()
    executor.add_tool(block, assistant_msg)

    async for _ in executor.get_remaining_results():
        pass

    updated_once = executor.get_updated_context()
    updated_twice = executor.get_updated_context()

    assert updated_once.messages == ["applied"]
    assert updated_twice.messages == ["applied"]
