# 示例

## 运行前准备

设置环境变量：

```bash
export OPENAI_API_KEY=your-api-key
export OPENAI_BASE_URL=https://api.openai.com/v1  # 可选
export OPENAI_MODEL=gpt-4o  # 可选
```

## 示例列表

### 1. simple_chat.py - 简单对话

最基本的对话示例，展示 SDK 的流式响应能力。

```bash
python examples/simple_chat.py
```

### 2. with_tools.py - 带工具调用

演示如何注册和使用工具。

```bash
python examples/with_tools.py
```

## 直接运行 SDK

```bash
python -m claude_core
```

需要先设置 `OPENAI_API_KEY` 环境变量。
