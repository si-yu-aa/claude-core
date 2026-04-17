#!/usr/bin/env python3
"""带工具调用的示例 - 演示如何使用内置工具"""

import asyncio
import os
from claude_core import QueryEngine, QueryEngineConfig, ToolImpl, ToolResult


class FileReadTool(ToolImpl):
    """文件读取工具"""

    name = "read_file"
    description = "读取文件内容"

    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "要读取的文件路径"
            }
        },
        "required": ["path"]
    }

    async def call(self, args, context, can_use_tool, on_progress):
        try:
            with open(args["path"], "r", encoding="utf-8") as f:
                content = f.read()
            return ToolResult(
                tool_use_id="",
                content=f"文件 {args['path']} 内容:\n\n{content[:1000]}..."  # 限制长度
            )
        except Exception as e:
            return ToolResult(
                tool_use_id="",
                content=f"读取文件失败: {str(e)}",
                is_error=True
            )


class CalculatorTool(ToolImpl):
    """计算器工具"""

    name = "calculate"
    description = "执行数学计算"

    input_schema = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "数学表达式，如 '2 + 2' 或 '10 * 5'"
            }
        },
        "required": ["expression"]
    }

    async def call(self, args, context, can_use_tool, on_progress):
        try:
            expression = args["expression"]
            # 安全计算（只允许基本运算）
            allowed_chars = set("0123456789+-*/.() ")
            if not all(c in allowed_chars for c in expression):
                return ToolResult(
                    tool_use_id="",
                    content="表达式包含非法字符",
                    is_error=True
                )
            result = eval(expression)
            return ToolResult(
                tool_use_id="",
                content=f"{expression} = {result}"
            )
        except Exception as e:
            return ToolResult(
                tool_use_id="",
                content=f"计算错误: {str(e)}",
                is_error=True
            )


async def main():
    api_key = os.getenv("OPENAI_API_KEY", "your-api-key-here")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("OPENAI_MODEL", "gpt-4o")

    print(f"使用模型: {model}")
    print("-" * 50)

    # 创建引擎
    config = QueryEngineConfig(
        api_key=api_key,
        base_url=base_url,
        model=model,
        max_turns=10,
    )

    engine = QueryEngine(config)

    # 注册工具
    engine.set_tools([FileReadTool(), CalculatorTool()])

    # 设置系统提示
    engine.set_system_prompt(
        "你是一个有帮助的助手。当用户要求时，你可以使用工具来完成任务。\n"
        "可用的工具:\n"
        "- read_file: 读取文件内容\n"
        "- calculate: 执行数学计算"
    )

    print("带工具调用的对话示例")
    print("-" * 50)

    # 示例问题
    questions = [
        "请计算 (15 + 25) * 2 等于多少?",
        # "请读取 /etc/hostname 文件（如果存在）",
    ]

    for q in questions:
        print(f"\n问: {q}")
        print("答: ", end="", flush=True)

        async for event in engine.submit_message(q):
            if isinstance(event, dict):
                if event.get("type") == "content":
                    print(event.get("content", ""), end="", flush=True)
                elif event.get("type") == "tool_use":
                    print(f"\n[调用工具: {event.get('name')}]", end="", flush=True)
                elif event.get("type") == "tool_result":
                    result = event.get("content", "")
                    print(f"\n[工具结果: {str(result)[:200]}]", end="", flush=True)

        print()


if __name__ == "__main__":
    print("=" * 50)
    print("Claude Core SDK 工具调用示例")
    print("=" * 50)
    asyncio.run(main())
