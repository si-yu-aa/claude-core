# Claude Core Python 移植设计

**日期**: 2026-04-16
**目标**: 将 Claude Code TypeScript 实现的核心内容移植为 Python

---

## 1. 概述与目标

### 1.1 项目定位

将 Claude Code 的核心功能（LLM 调用链路、Tool 系统、Agent 系统、上下文管理、Prompt 管理）用 Python 重新实现为一个可嵌入的 SDK。

### 1.2 设计原则

- **架构对照**: 保持与原版 TypeScript 相同的模块结构和命名，1:1 映射
- **Python 风格**: 用 Python 惯用法（dataclass、async/await、Protocol）重写
- **功能完整**: 不遗漏任何核心细节

### 1.3 技术选型

- **运行时**: Python 3.11+
- **异步框架**: asyncio (原生)
- **HTTP 客户端**: httpx (支持 async 和流式)
- **类型提示**: dataclass、Protocol、TypeVar
- **验证**: pydantic
- **API 兼容**: OpenAI Chat Completions 协议，base_url 可配置

---

## 2. 项目结构

```
claude-core/
├── pyproject.toml
├── src/
│   └── claude_core/
│       ├── __init__.py
│       ├── api/                        # LLM API 调用层
│       │   ├── __init__.py
│       │   ├── client.py              # OpenAI 兼容客户端
│       │   ├── streaming.py           # 流式响应处理
│       │   ├── types.py              # API 类型定义
│       │   └── errors.py             # 错误处理和重试
│       │
│       ├── models/                    # 数据模型
│       │   ├── __init__.py
│       │   ├── message.py            # 消息类型体系
│       │   ├── tool.py               # Tool 类型定义
│       │   ├── context.py            # 上下文类型
│       │   └── events.py             # 流事件类型
│       │
│       ├── engine/                    # 核心 Query Engine
│       │   ├── __init__.py
│       │   ├── query_engine.py       # QueryEngine 主类
│       │   ├── query_loop.py         # query() 异步生成器
│       │   ├── transitions.py        # 状态转换
│       │   ├── config.py             # 查询配置
│       │   ├── deps.py              # 依赖注入
│       │   └── types.py             # 引擎内部类型
│       │
│       ├── tools/                     # Tool 系统
│       │   ├── __init__.py
│       │   ├── base.py              # Tool 基类和 Protocol
│       │   ├── registry.py          # Tool 注册表
│       │   ├── executor.py          # 基础 Tool 执行器
│       │   ├── streaming_executor.py # 流式 Tool 执行器
│       │   ├── orchestrator.py      # 工具编排
│       │   ├── permission.py        # 权限系统
│       │   ├── hooks.py             # Pre/Post Tool Hooks
│       │   ├── progress.py          # 进度事件
│       │   └── builtin/             # 内置工具实现
│       │       ├── __init__.py
│       │       ├── file_read.py
│       │       ├── file_write.py
│       │       ├── file_edit.py
│       │       ├── glob.py
│       │       ├── grep.py
│       │       ├── bash.py
│       │       ├── web_search.py
│       │       ├── web_fetch.py
│       │       ├── agent.py
│       │       └── task.py
│       │
│       ├── context/                   # 上下文管理
│       │   ├── __init__.py
│       │   ├── manager.py           # 上下文管理器
│       │   ├── compression.py       # 自动压缩/摘要
│       │   ├── budget.py            # Token 预算管理
│       │   ├── attachments.py       # 附件处理
│       │   ├── microcompact.py      # 微压缩
│       │   ├── snip.py             # 历史裁剪
│       │   └── collapse.py         # 上下文折叠
│       │
│       ├── agents/                   # Agent 系统
│       │   ├── __init__.py
│       │   ├── base.py             # Agent 基类
│       │   ├── worker.py           # Worker Agent
│       │   ├── session.py          # Agent Session
│       │   ├── mailbox.py         # 消息邮箱
│       │   └── types.py           # Agent 相关类型
│       │
│       ├── prompt/                   # Prompt 管理
│       │   ├── __init__.py
│       │   ├── builder.py         # System Prompt 构建
│       │   ├── templates.py       # Prompt 模板
│       │   ├── manager.py         # Prompt 管理器
│       │   └── parts.py          # Prompt 组件
│       │
│       ├── mcp/                     # MCP 协议支持
│       │   ├── __init__.py
│       │   ├── client.py         # MCP 客户端
│       │   ├── types.py          # MCP 类型
│       │   └── normalizer.py     # 工具名规范化
│       │
│       └── utils/                   # 工具函数
│           ├── __init__.py
│           ├── tokens.py         # Token 计算
│           ├── uuid.py           # UUID 生成
│           ├── logging.py        # 日志
│           ├── abort.py          # AbortController
│           └── stream.py         # 异步流工具
│
└── tests/
```

---

## 3. 核心组件详细设计

### 3.1 API 层 (`api/`)

#### LLMClient

```python
class LLMClient:
    """OpenAI 兼容的 LLM 客户端"""

    def __init__(
        self,
        base_url: str,              # 可配置的 API base URL
        api_key: str,
        model: str = "gpt-4o",
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def chat(
        self,
        messages: list[MessageParam],
        tools: list[ToolParam] | None = None,
        stream: bool = True,
        **kwargs,
    ) -> AsyncGenerator[StreamEvent, None]:
        """发送聊天请求，返回流式响应"""
        ...

    async def chat_completion(
        self,
        messages: list[MessageParam],
        tools: list[ToolParam] | None = None,
        **kwargs,
    ) -> ChatCompletion:
        """非流式聊天完成"""
        ...
```

**关键特性**:
- 支持 OpenAI Chat Completions 协议
- 可配置 base_url（支持 Ollama、vLLM、DeepSeek 等）
- 流式响应处理（Server-Sent Events）
- 自动重试和错误处理
- 请求/响应日志

---

### 3.2 数据模型 (`models/`)

#### Message 类型体系

```python
from dataclasses import dataclass, field
from typing import Literal, Any

MessageType = Literal["user", "assistant", "system", "attachment", "progress", "grouped_tool_use"]

@dataclass
class Message:
    type: MessageType
    uuid: str
    is_meta: bool = False
    is_compact_summary: bool = False
    tool_use_result: Any = None
    message: dict = field(default_factory=dict)

@dataclass
class UserMessage(Message):
    type: Literal["user"] = "user"
    image_paste_ids: list[int] | None = None

@dataclass
class AssistantMessage(Message):
    type: Literal["assistant"] = "assistant"

@dataclass
class SystemMessage(Message):
    type: Literal["system"] = "system"

@dataclass
class AttachmentMessage(Message):
    type: Literal["attachment"] = "attachment"
    attachment: dict = field(default_factory=dict)

@dataclass
class ProgressMessage(Message):
    type: Literal["progress"] = "progress"
    data: Any = None

@dataclass
class ToolResult:
    tool_use_id: str
    content: str | list[dict]
    is_error: bool = False
```

---

### 3.3 Tool 系统 (`tools/`)

#### Tool Protocol

```python
from typing import Protocol, AsyncGenerator, Callable, Any
from dataclasses import dataclass

class Tool(Protocol):
    """Tool 接口定义"""

    name: str
    description: str
    input_schema: "InputSchema"

    async def call(
        self,
        args: dict[str, Any],
        context: "ToolUseContext",
        can_use_tool: "CanUseToolFn",
        on_progress: "ToolCallProgress | None" = None,
    ) -> "ToolResult":
        """执行工具"""
        ...

    def is_enabled(self) -> bool:
        """工具是否启用"""
        return True

    def is_concurrency_safe(self, args: dict[str, Any]) -> bool:
        """是否并发安全（可并行执行）"""
        return False

    def is_read_only(self, args: dict[str, Any]) -> bool:
        """是否是只读操作"""
        return False

    def is_destructive(self, args: dict[str, Any]) -> bool:
        """是否是不可逆操作"""
        return False

    def interrupt_behavior(self) -> Literal["cancel", "block"]:
        """用户新消息时的行为：cancel=停止，block=阻塞"""
        return "block"

    async def validate_input(
        self, input_data: dict[str, Any], context: "ToolUseContext"
    ) -> "ValidationResult":
        """验证输入"""
        ...

    async def check_permissions(
        self, input_data: dict[str, Any], context: "ToolUseContext"
    ) -> "PermissionResult":
        """检查权限"""
        return PermissionResult(behavior="allow", updated_input=input_data)

    def prompt(self, options: "PromptOptions") -> str:
        """生成工具的 prompt 描述"""
        ...
```

#### StreamingToolExecutor

**核心职责**: 当 LLM 流式返回 tool_use 块时，立即开始执行工具，支持并发控制。

```python
from enum import Enum
from dataclasses import dataclass, field

class ToolStatus(Enum):
    QUEUED = "queued"
    EXECUTING = "executing"
    COMPLETED = "completed"
    YIELDED = "yielded"

@dataclass
class TrackedTool:
    id: str
    block: "ToolUseBlock"
    assistant_message: "AssistantMessage"
    status: ToolStatus = ToolStatus.QUEUED
    is_concurrency_safe: bool = False
    promise: asyncio.Task | None = field(default=None)
    results: list[Message] = field(default_factory=list)
    pending_progress: list[Message] = field(default_factory=list)
    context_modifiers: list[Callable] = field(default_factory=list)

class StreamingToolExecutor:
    """
    流式 Tool 执行器

    关键特性：
    1. 边接收边执行：tool_use 块到达时立即开始执行
    2. 并发控制：isConcurrencySafe=True 可并行，False 独占
    3. 进度追踪：实时 yield 进度消息
    4. 中断处理：支持用户中断、兄弟工具错误传播
    5. Streaming Fallback：模型降级时丢弃未完成工具
    """

    def __init__(
        self,
        tool_definitions: list[Tool],
        can_use_tool: "CanUseToolFn",
        tool_use_context: "ToolUseContext",
    ):
        self._tools: list[TrackedTool] = []
        self._tool_definitions = tool_definitions
        self._can_use_tool = can_use_tool
        self._context = tool_use_context
        self._has_errored = False
        self._sibling_abort_controller = create_child_abort_controller(
            tool_use_context.abort_controller
        )
        self._discarded = False

    def add_tool(self, block: "ToolUseBlock", assistant_message: "AssistantMessage") -> None:
        """添加工具到执行队列"""
        ...

    async def get_remaining_results(self) -> AsyncGenerator[MessageUpdate, None]:
        """等待所有工具完成，yield 结果和进度"""
        ...
```

#### ToolOrchestrator

```python
async def run_tools(
    tool_use_blocks: list["ToolUseBlock"],
    assistant_messages: list["AssistantMessage"],
    can_use_tool: "CanUseToolFn",
    tool_use_context: "ToolUseContext",
) -> AsyncGenerator[MessageUpdate, None]:
    """
    工具编排器

    职责：
    1. 将工具分批（并发安全 vs 非并发安全）
    2. 并发安全工具并行执行
    3. 非并发安全工具串行执行
    4. 维护工具执行上下文
    """
    ...

def partition_tool_calls(
    tool_use_blocks: list["ToolUseBlock"],
    context: "ToolUseContext",
) -> list[Batch]:
    """将工具分批：单个非只读工具独占一批，多个连续只读工具合并为一批"""
    ...
```

#### 权限系统

```python
@dataclass
class ToolPermissionContext:
    mode: "PermissionMode"
    additional_working_directories: dict[str, "AdditionalWorkingDirectory"]
    always_allow_rules: dict[str, list[str]]
    always_deny_rules: dict[str, list[str]]
    always_ask_rules: dict[str, list[str]]
    is_bypass_permissions_mode_available: bool
    is_auto_mode_available: bool = False
    should_avoid_permission_prompts: bool = False

@dataclass
class PermissionResult:
    behavior: Literal["allow", "deny", "ask"]
    updated_input: dict | None = None
    decision_classification: str | None = None

@dataclass
class ValidationResult:
    result: bool
    message: str = ""
    error_code: int = 0
```

---

### 3.4 Query Engine (`engine/`)

#### QueryEngine

```python
class QueryEngine:
    """
    高级查询引擎，管理对话生命周期和会话状态

    职责：
    - 管理会话消息历史
    - 处理用户输入
    - 管理文件状态缓存
    - 跟踪 API 使用
    - 处理权限和拒绝
    """

    def __init__(self, config: QueryEngineConfig):
        self._config = config
        self._messages: list[Message] = []
        self._abort_controller = AbortController()
        self._permission_denials: list[SDKPermissionDenial] = []
        self._total_usage: Usage = EMPTY_USAGE

    async def submit_message(
        self,
        content: str,
        attachments: list[Attachment] | None = None,
    ) -> AsyncGenerator[Event, None]:
        """提交用户消息，返回事件流"""
        ...

    async def ask(self, prompt: str, **kwargs) -> str:
        """简单的阻塞式 ask 接口"""
        results = []
        async for event in self.submit_message(prompt):
            if isinstance(event, Message):
                results.append(event)
        return self._extract_response(results)
```

#### Query Loop

```python
async def query(
    params: QueryParams,
) -> AsyncGenerator[StreamEvent | Message, Terminal]:
    """
    核心 query 异步生成器

    完整流程：
    1. 初始化（Langfuse trace, token budget tracker, memory prefetch）
    2. 主循环：
       a) 上下文预处理（压缩、预算检查）
       b) API 调用（流式）
       c) 错误处理（prompt-too-long, max-output-tokens, 模型降级）
       d) 工具执行（StreamingToolExecutor 或 runTools）
       e) 后处理（摘要生成、附件、停止钩子）
       f) 循环继续或结束
    """
    ...

@dataclass
class QueryParams:
    messages: list[Message]
    system_prompt: SystemPrompt
    user_context: dict[str, str]
    system_context: dict[str, str]
    can_use_tool: CanUseToolFn
    tool_use_context: ToolUseContext
    fallback_model: str | None = None
    query_source: str = "sdk"
    max_output_tokens_override: int | None = None
    max_turns: int | None = None
    skip_cache_write: bool = False
    task_budget: dict | None = None

@dataclass
class QueryState:
    messages: list[Message]
    tool_use_context: ToolUseContext
    max_output_tokens_recovery_count: int = 0
    has_attempted_reactive_compact: bool = False
    max_output_tokens_override: int | None = None
    pending_tool_use_summary: "Promise[ToolUseSummaryMessage] | None" = None
    stop_hook_active: bool | None = None
    turn_count: int = 1
    transition: "Continue | None" = None
```

---

### 3.5 上下文管理 (`context/`)

#### ContextManager

```python
class ContextManager:
    """
    上下文管理器，处理上下文窗口和压缩

    压缩策略：
    1. AutoCompact - 自动压缩（阈值触发）
    2. Microcompact - 微压缩（编辑过的缓存消息）
    3. Snip - 历史裁剪（移除中间消息）
    4. Collapse - 上下文折叠（保留关键点）
    5. Reactive Compact - 响应式压缩（413 错误后触发）
    """

    def __init__(self, max_tokens: int, model: str):
        self._max_tokens = max_tokens
        self._model = model

    async def should_compact(
        self, messages: list[Message], token_count: int
    ) -> bool:
        """判断是否需要压缩"""
        ...

    async def compact(
        self, messages: list[Message], system_prompt: SystemPrompt, context: ToolUseContext
    ) -> CompactionResult:
        """执行上下文压缩"""
        ...

@dataclass
class CompactionResult:
    summary_messages: list[Message]
    attachments: list[Attachment]
    hook_results: list[Message]
    pre_compact_token_count: int
    post_compact_token_count: int
    true_post_compact_token_count: int
    compaction_usage: Usage | None
```

---

### 3.6 Agent 系统 (`agents/`)

#### WorkerAgent

```python
class WorkerAgent:
    """
    Worker Agent - 用于子任务委托

    关键特性：
    1. 独立的 tool_use_context
    2. 嵌套的 query tracking（chainId + depth）
    3. 消息邮箱机制
    4. 生命周期管理
    """

    def __init__(
        self,
        config: "AgentConfig",
        parent_context: "ToolUseContext",
    ):
        self.agent_id = generate_agent_id()
        self.config = config
        self.parent_context = parent_context
        self.context = self._create_subagent_context()
        self.mailbox = Mailbox()
        self.status = AgentStatus.IDLE

    async def run(self, task: str) -> "AgentResult":
        """运行子 agent 执行任务"""
        ...

    async def stop(self) -> None:
        """停止子 agent"""
        ...

@dataclass
class AgentConfig:
    name: str
    description: str
    system_prompt: SystemPrompt
    tools: list[Tool]
    model: str | None = None
    max_turns: int | None = None

@dataclass
class AgentResult:
    agent_id: str
    messages: list[Message]
    final_response: str
```

---

### 3.7 Prompt 管理 (`prompt/`)

#### SystemPromptBuilder

```python
class SystemPromptBuilder:
    """
    System Prompt 构建器

    组合多个部分：
    1. 基础指令
    2. 工具定义（JSON Schema）
    3. 工具使用规则
    4. Agent 定义
    5. 用户上下文
    6. 系统上下文
    """

    def __init__(
        self,
        base_instructions: str,
        tools: list[Tool],
        agents: list[AgentDefinition] | None = None,
    ):
        self.base_instructions = base_instructions
        self.tools = tools
        self.agents = agents or []

    def build(
        self,
        user_context: dict[str, str],
        system_context: dict[str, str],
    ) -> str:
        """构建完整的 system prompt"""
        parts = [
            self._build_base_section(),
            self._build_tools_section(),
            self._build_agents_section(),
            self._build_context_section(user_context, system_context),
        ]
        return "\n\n".join(filter(None, parts))
```

---

## 4. 数据流

```
用户输入
    ↓
QueryEngine.submit_message()
    ↓
query() [AsyncGenerator]
    ├─ 上下文预处理 (压缩、预算检查)
    ├─ callModel() → LLM API (流式)
    │   ↓
    │   流式响应处理
    │   ├─ Assistant 消息块
    │   └─ Tool_use 块 → StreamingToolExecutor.add_tool()
    │       ↓
    │       并发/串行执行工具
    │       ↓
    │       进度消息实时 yield
    │       ↓
    │       工具结果
    ├─ 工具结果返回 LLM
    └─ 循环直到 stop_reason
    ↓
返回最终响应
```

---

## 5. 错误处理

| 错误类型 | 处理策略 |
|---------|---------|
| API 错误 | 重试机制、模型降级 |
| Tool 执行错误 | 捕获、报告、继续 |
| 上下文溢出 | 自动压缩、提示用户 |
| 权限拒绝 | 记录、通知用户 |
| Prompt-too-long | Reactive compact、collapse drain |
| Max-output-tokens | 升级重试（8k → 64k）、多轮恢复 |

---

## 6. 内置工具

| 工具名 | 描述 | 并发安全 |
|-------|------|---------|
| FileRead | 读取文件 | Yes |
| FileWrite | 写入文件 | No |
| FileEdit | 编辑文件 | No |
| Glob | 文件搜索 | Yes |
| Grep | 内容搜索 | Yes |
| Bash | 执行命令 | No |
| WebSearch | 网络搜索 | Yes |
| WebFetch | 网页抓取 | Yes |
| Agent | 子 Agent 委托 | No |
| TaskCreate | 创建任务 | No |
| TaskUpdate | 更新任务 | No |
| TaskList | 列出任务 | Yes |
| TaskGet | 获取任务 | Yes |

---

## 7. 实现优先级

### Phase 1: 核心基础设施
1. 数据模型（Message, Tool, Context types）
2. API 客户端（LLMClient）
3. 工具函数（AbortController, Stream, UUID, Tokens）
4. Tool 基类和 Protocol

### Phase 2: Tool 系统
1. Tool 注册表
2. 基础 Tool 执行器
3. 流式 Tool 执行器（StreamingToolExecutor）
4. 工具编排器（ToolOrchestrator）
5. 权限系统
6. 内置工具实现

### Phase 3: Query Engine
1. QueryParams 和 QueryState
2. query() 异步生成器
3. QueryEngine 主类
4. 状态转换（transitions）

### Phase 4: 上下文管理
1. Token 计算
2. 上下文管理器
3. 压缩策略实现
4. Token 预算管理

### Phase 5: Agent 系统
1. WorkerAgent
2. Agent Session
3. 消息邮箱

### Phase 6: Prompt 管理
1. SystemPromptBuilder
2. Prompt 模板
3. Prompt 管理器

---

## 8. 测试策略

- 单元测试：每个模块独立测试
- 集成测试：API 调用、Tool 执行流程测试
- 对照测试：与原版 TypeScript 行为对比
