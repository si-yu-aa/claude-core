#!/usr/bin/env python3
"""简单的对话示例 - 演示 Claude Core SDK 基本用法"""

import asyncio
import os
from claude_core import QueryEngine, QueryEngineConfig


async def main():
    # 从环境变量获取 API key，或直接填写
    api_key = os.getenv("OPENAI_API_KEY", "your-api-key-here")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("OPENAI_MODEL", "gpt-4o")

    print(f"使用模型: {model}")
    print(f"API 地址: {base_url}")
    print("-" * 50)

    # 创建引擎配置
    config = QueryEngineConfig(
        api_key=api_key,
        base_url=base_url,
        model=model,
        max_turns=10,
    )

    # 创建 QueryEngine
    engine = QueryEngine(config)

    # 设置系统提示
    engine.set_system_prompt("你是一个有帮助的助手，用简洁的语言回答问题。")

    print("开始对话（输入 'quit' 退出）")
    print("-" * 50)

    while True:
        try:
            # 获取用户输入
            user_input = input("\n你: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("再见!")
                break

            # 发送消息并打印响应
            print("\n助手: ", end="", flush=True)

            async for event in engine.submit_message(user_input):
                if isinstance(event, dict):
                    if event.get("type") == "content":
                        print(event.get("content", ""), end="", flush=True)
                    elif event.get("type") == "tool_use":
                        print(f"\n[调用工具: {event.get('name')}]", end="", flush=True)
                    elif event.get("type") == "tool_result":
                        result = event.get("content", "")
                        if isinstance(result, list):
                            for r in result:
                                if isinstance(r, dict) and r.get("type") == "tool_result":
                                    print(f"\n[工具结果: {r.get('content', '')[:100]}...]", end="")
                        else:
                            print(f"\n[工具结果: {str(result)[:100]}...]", end="")
                    elif event.get("type") == "error":
                        print(f"\n[错误: {event.get('error')}]", end="")
                elif hasattr(event, 'type'):
                    if event.type == "content_block_delta":
                        print(event.delta.get("content", ""), end="", flush=True)

            print()

        except KeyboardInterrupt:
            print("\n\n对话被中断")
            break
        except Exception as e:
            print(f"\n错误: {e}")


if __name__ == "__main__":
    print("=" * 50)
    print("Claude Core SDK 简单对话示例")
    print("=" * 50)
    asyncio.run(main())
