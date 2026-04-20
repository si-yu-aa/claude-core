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
    provider = os.getenv("CLAUDE_CORE_PROVIDER", "openai")
    api_key_env = "GEMINI_API_KEY" if provider == "gemini" else "OPENAI_API_KEY"
    default_base_url = (
        "https://generativelanguage.googleapis.com/v1beta/openai"
        if provider == "gemini"
        else "https://api.openai.com/v1"
    )

    api_key = os.getenv(api_key_env)
    if not api_key:
        print(f"错误: 请设置 {api_key_env} 环境变量")
        print(f"  export {api_key_env}=your-api-key")
        return

    base_url = os.getenv("OPENAI_BASE_URL", default_base_url)
    model = os.getenv("OPENAI_MODEL", "gpt-4o")

    print(f"Claude Core SDK")
    print(f"Provider: {provider}")
    print(f"模型: {model}")
    print(f"API: {base_url}")
    print("-" * 50)

    config = QueryEngineConfig(
        api_key=api_key,
        provider=provider,
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
