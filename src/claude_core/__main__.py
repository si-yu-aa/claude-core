#!/usr/bin/env python3
"""
Claude Core SDK - 直接运行入口

用法:
    python -m claude_core

这将启动一个简单的交互式对话。
"""

import asyncio
import os
from claude_core import QueryEngine, QueryEngineConfig


async def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("错误: 请设置 OPENAI_API_KEY 环境变量")
        print("  export OPENAI_API_KEY=your-api-key")
        return

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("OPENAI_MODEL", "gpt-4o")

    print(f"Claude Core SDK")
    print(f"模型: {model}")
    print(f"API: {base_url}")
    print("-" * 50)

    config = QueryEngineConfig(
        api_key=api_key,
        base_url=base_url,
        model=model,
    )

    engine = QueryEngine(config)

    print("开始对话...")
    print()

    user_input = input("你: ").strip()
    if not user_input:
        return

    print("助手: ", end="", flush=True)

    async for event in engine.submit_message(user_input):
        if isinstance(event, dict):
            if event.get("type") == "content":
                print(event.get("content", ""), end="", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
