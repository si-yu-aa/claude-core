# Claude Core Python 移植对比分析

**日期**: 2026-04-16
**目标**: 对比分析 Python 实现与 TypeScript 原版的差异

---

## 1. 概述

| 指标 | Python (claude-core) | TypeScript (claude-code) | 完成度 |
|------|---------------------|-------------------------|--------|
| **代码行数** | ~3,500 行 | ~50,000+ 行 | ~7% |
| **工具数量** | 7 个内置工具 | 55+ 工具目录 | ~13% |
| **特性** | 核心功能原型 | 生产级完整实现 | - |
| **架构** | 简化层次架构 | 特性开关驱动的复杂架构 | - |

---

## 2. API 层 (`api/`)

### 2.1 功能对比

| 功能 | Python | TypeScript |
|------|--------|------------|
| **Provider 支持** | 仅 OpenAI 兼容 | 7 种: firstParty, bedrock, vertex, foundry, openai, gemini, grok |
| **认证** | 仅 API Key | OAuth, AWS 凭证(自动刷新), GCP, Azure AD |
| **重试** | 3 次简单重试 | 指数退避, `withRetry.ts` |
| **流式处理** | 基础 SSE 解析 | Provider 适配器 (openai/gemini/grok) |
| **错误处理** | 5 种错误类型 | 20+ 分类, 上下文感知消息 |

### 2.2 缺失功能

- 多 Provider 支持
- OAuth 认证流程
- AWS/GCP 凭证自动刷新
- 请求日志调试
- Rate limit header 解析
- Prompt caching headers
- Usage 跟踪和成本计算

### 2.3 代码量差异

| 文件 | Python | TypeScript |
|------|--------|-----------|
| API Client | ~100 行 | ~400+ 行, 7 providers |
| 错误处理 | ~50 行, 5 类型 | ~900 行, 20+ 分类 |
| 流式处理 | ~55 行, 4 事件类型 | 每 API 一个适配器 |

---

## 3. 数据模型 (`models/`)

### 3.1 Message 类型

| Python | TypeScript |
|--------|-----------|
| 6 种消息类型 | 25+ 变体 |
| Dataclass 继承 | Discriminant union types |
| 简单 `dict` content | 类型的 `ContentBlock[]` |

**TypeScript 独有**:
- `CollapsedReadSearchGroup` (git/hook/memory 统计)
- `GroupedToolUseMessage`
- `RenderableMessage` / `CollapsibleMessage`
- 系统消息子类型 (error, metrics, permission)

### 3.2 Tool 类型

| Python | TypeScript |
|--------|-----------|
| `ToolDefinition` (仅接口) | `Tool.ts` 完整定义, 50+ 可选方法 |
| `ToolUseContext` (桩) | 实际实现带完整属性 |
| `InputSchema = Any` | Zod schemas |

---

## 4. Tool 系统 (`tools/`)

### 4.1 Tool Protocol

| 方面 | Python | TypeScript |
|------|--------|------------|
| **类型系统** | Duck-typed Protocol | 结构化类型, Zod schemas, 泛型 |
| **输入验证** | 手动 in `call()` | `validateInput()` hook, Zod 验证 |
| **权限系统** | 无 | `checkPermissions()`, deny rules, `ToolPermissionContext` |
| **UI 渲染** | 无 | 10+ 渲染方法 |
| **进度报告** | `on_progress` 参数存在但未使用 | `pendingProgress` 消息, `progressAvailableResolve` |
| **MCP 支持** | 无 | 一等公民, `mcpInfo`, server prefixes |

### 4.2 StreamingToolExecutor

| 方面 | Python (~310行) | TypeScript (~540行) |
|------|----------------|-------------------|
| **可观测性** | 无 | Langfuse tracing |
| **中断行为** | 简单 abort | `getToolInterruptBehavior()` per-tool |
| **Abort 传播** | 信号传播 | Bubble up to query controller |
| **工具追踪** | 无 | `setInProgressToolUseIDs` |
| **Bash 错误处理** | 设置 `hasErrored` | 特殊处理, 取消 siblings |

### 4.3 内置工具对比

#### FileRead

| 功能 | Python | TypeScript |
|------|--------|------------|
| **复杂度** | ~76 行 | ~1180 行 |
| **功能** | 100KB 截断, 纯文本 | 图片 base64, PDF, Notebook, 行偏移/限制 |
| **缓存** | 无 | `readFileState` with mtime |
| **权限** | 无 | `checkReadPermissionForTool()` |
| **安全** | 无 | 设备文件阻塞, UNC 安全 |

#### FileWrite

| 功能 | Python | TypeScript |
|------|--------|------------|
| **复杂度** | ~67 行 | ~435 行 |
| **功能** | 基本写入 | 原子写入, encoding 保留, structured diffs |
| **Git** | 无 | `gitDiff` 获取 |
| **通知** | 无 | VSCode diff, LSP |

#### FileEdit

| 功能 | Python | TypeScript |
|------|--------|------------|
| **复杂度** | ~100 行 | ~625 行 |
| **替换** | 单次 `str.replace()` | `replace_all` 选项 |
| **匹配** | 无 | multi-match 检测, quote normalization |
| **原子性** | 无 | mkdir → fileHistory → write → LSP |

#### Bash

| 功能 | Python | TypeScript |
|------|--------|------------|
| **复杂度** | ~107 行 | ~1000+ 行 |
| **Shell 抽象** | 无 | `packages/shell/` |
| **进度报告** | 无 | 丰富进度 |
| **权限** | 无 | 完整集成 |

#### Task 工具

| 功能 | Python | TypeScript |
|------|--------|------------|
| **存储** | 内存 dict | Zustand store (持久化) |
| **工具** | 4 个 | 6 个 (加 TaskStop, TaskOutput) |

### 4.4 缺失功能汇总

1. 无 Zod-style schema 验证
2. 无权限系统 (deny rules, checkPermissions)
3. 无 UI 渲染 (React components)
4. 无进度报告
5. 无 MCP tool 支持
6. 无 `readFileState` 缓存
7. 无 Langfuse tracing
8. 无 per-tool interrupt behavior
9. 无 `validateInput()` hook
10. 无特性开关系统
11. 无 tool aliases / `shouldDefer` / `alwaysLoad`
12. 无 LSP 通知
13. 无文件历史追踪
14. Task tools 无持久化存储

---

## 5. Query Engine (`engine/`)

### 5.1 功能完整性

| 方面 | Python | TypeScript |
|------|--------|------------|
| **query() 行数** | ~196 行 (不完整, 早期 break) | ~1773 行 |
| **Tool 执行** | 占位符, 仅提取 tools | `StreamingToolExecutor` + 并行执行 |
| **错误恢复** | 无 | 4 种恢复策略 |
| **压缩** | 简单 keep-recent/summarize-older | 5 种策略 |
| **流式** | 基础 | 流式工具执行 |
| **Budget 跟踪** | `TokenBudget` 类 | `createBudgetTracker()` + diminishing returns |
| **Hooks** | 无 | post-sampling, stop hooks |
| **特性开关** | 无 | 19 个 flags |
| **SDK 接口** | 仅 `ask()` wrapper | 完整 SDK 类型 |

### 5.2 缺失功能

1. **query() 不完整** - 第 196 行 break, 实际循环体缺失
2. **无实际 tool 执行** - 仅提取, 不执行
3. **无错误恢复** - 无 prompt-too-long, max-output, media recovery
4. **单压缩策略** - 简单 summarize
5. **无流式工具执行** - 无 `StreamingToolExecutor`
6. **无特性开关** - 全部启用
7. **无 hooks**
8. **无 model fallback**
9. **无 snip / microcompact / context collapse**

---

## 6. Context 管理 (`context/`)

### 6.1 功能对比

| 方面 | Python | TypeScript |
|------|--------|------------|
| **压缩** | 简单 summarize | 5 种策略 (snip, autocompact, reactive, collapse, microcompact) |
| **模型支持** | 硬编码 "gpt-4o" | 完整模型矩阵 |
| **1M context** | 无 | `has1mContext()`, `modelSupports1M()` |
| **输出限制** | 无 | Per-model defaults and upper limits |

### 6.2 TypeScript 压缩策略

| 策略 | Feature Flag | 说明 |
|------|-------------|------|
| AutoCompact | 始终启用 | 阈值触发的自动压缩 |
| SnipCompact | `HISTORY_SNIP` | 历史裁剪, 移除中间消息 |
| ReactiveCompact | `REACTIVE_COMPACT` | 413 错误后响应式压缩 |
| ContextCollapse | `CONTEXT_COLLAPSE` | 保留关键点的上下文折叠 |
| Microcompact | - | 编辑过的缓存消息的微压缩 |

---

## 7. Agent 系统 (`agents/`)

### 7.1 功能对比

| 方面 | Python | TypeScript |
|------|--------|------------|
| **实现** | 占位符/scaffold | 生产级, fork subagents, swarms |
| **WorkerAgent.run()** | 返回 `"Agent {name} processed task: {task}"` | 实际查询执行 |
| **Context 传播** | 简单 mailbox | `AsyncLocalStorage` + subagent/teammate contexts |
| **Fork 机制** | 无 | Parent context 继承, worktree 隔离 |
| **分析** | 无 | `tengu_agent_tool_completed` 等事件 |
| **Tool 过滤** | 无 | 基于权限模式过滤 |

### 7.2 缺失功能

1. 无实际 query 执行
2. 无 nested agent tracking (chainId, depth)
3. 无 abort controller 集成
4. 无 subagent context 传播
5. `pause()` / `resume()` 是空操作
6. 无 fork 机制
7. 无 AsyncLocalStorage context
8. 无分析集成
9. 无基于权限的 tool 过滤

---

## 8. Prompt 管理 (`prompt/`)

### 8.1 功能对比

| 方面 | Python | TypeScript |
|------|--------|------------|
| **构建方式** | 静态模板 | 6 级优先级动态系统 |
| **Coordinator 模式** | 无 | `getCoordinatorSystemPrompt()` |
| **Proactive 模式** | 无 | Agent prompts 追加而非替换 |
| **CLAUDE.md 发现** | 无 | `getClaudeMds()` |
| **Git 集成** | 无 | Branch, status, recent commits |
| **特性开关** | 无 | `COORDINATOR_MODE`, `PROACTIVE`, `KAIROS` |

### 8.2 优先级系统 (TypeScript)

```
override > coordinator > agent > custom > default (+ append)
```

### 8.3 缺失功能

1. 无优先级 prompt 解析
2. 无 coordinator 模式
3. 无 proactive 模式
4. 无 CLAUDE.md 文件发现
5. 无 git 上下文
6. 无特性开关系统
7. 无分析集成

---

## 9. Utils (`utils/`)

### 9.1 功能对比

| 方面 | Python | TypeScript |
|------|--------|------------|
| **AbortController** | 基础实现 | 带错误类型的完整实现 |
| **Token 计数** | 简单 `/4` | `tokenCountWithEstimation()`, `getTokenCountFromUsage()` |
| **Agent ID** | 简单 UUID | 类型的 `asAgentId()` |
| **Swarm** | 无 | `agentSwarmsEnabled()` |

### 9.2 缺失功能

1. 无类型化 Agent ID
2. 无 swarm 启用检查
3. 无 agentic session search
4. 无精细的 token 跟踪

---

## 10. 总体评估

### 10.1 Python 实现状态

| 组件 | 状态 | 说明 |
|------|------|------|
| API Client | 功能原型 | 基础 OpenAI 兼容, 缺少多 provider |
| 数据模型 | 基本完成 | Message/Tool 类型, 缺少复杂变体 |
| Tool Protocol | 基本完成 | 简单实现, 缺少权限/验证 hooks |
| StreamingToolExecutor | 核心实现 | 完整并发控制, 缺少 tracing/interrupt |
| 内置工具 | 部分完成 | FileRead/Write/Edit/Glob/Grep/Bash/Task, 缺少复杂功能 |
| Query Engine | 不完整 | `query()` 在第 196 行 break, 无实际循环 |
| Context Manager | 基础 | 简单压缩, 无多种策略 |
| Agent 系统 | 占位符 | 仅 scaffold, 无实际执行 |
| Prompt Builder | 基础 | 静态模板, 无动态优先级 |

### 10.2 TypeScript 独有功能汇总

1. **多 Provider 支持** (bedrock, vertex, foundry, gemini, grok)
2. **OAuth/AWS/GCP 认证**
3. **19 个特性开关**
4. **5 种压缩策略**
5. **流式工具执行**
6. **Model fallback**
7. **完整权限系统**
8. **Langfuse tracing**
9. **分析事件**
10. **UI 渲染系统**
11. **MCP 一等公民支持**
12. **LSP 集成**
13. **Git 上下文**
14. **CLAUDE.md 发现**
15. **Fork subagent 机制**
16. **Tool aliases / shouldDefer / alwaysLoad**
17. **File state cache (readFileState)**
18. **原子文件操作**
19. **VSCode 通知**

### 10.3 下一步建议

**高优先级**:
1. 完成 `query()` 循环体
2. 实现实际 tool 执行
3. 添加错误恢复 (prompt-too-long, max-output)

**中优先级**:
4. 实现权限系统
5. 添加特性开关
6. 实现多种压缩策略

**低优先级**:
7. Langfuse tracing
8. 分析集成
9. 多 Provider 支持

---

## 11. 文件映射

| Python (claude-core) | TypeScript (claude-code) |
|---------------------|------------------------|
| `api/client.py` | `services/api/claude.ts` |
| `api/errors.py` | `services/api/errors.ts` |
| `api/streaming.py` | `services/api/*/streamAdapter.ts` |
| `models/message.py` | `types/message.ts` |
| `models/tool.py` | `types/tool.ts`, `services/api/src/Tool.ts` |
| `tools/base.py` | `Tool.ts`, `tools.ts` |
| `tools/registry.py` | `tools.ts` (getTools, assembleToolPool) |
| `tools/streaming_executor.py` | `services/tools/StreamingToolExecutor.ts` |
| `tools/builtin/*` | `packages/builtin-tools/src/tools/*/` |
| `engine/query_engine.py` | `QueryEngine.ts` |
| `engine/query_loop.py` | `query.ts` |
| `context/manager.py` | `services/compact/*.ts` |
| `agents/worker.py` | `AgentTool/`, `forkSubagent.ts` |
| `prompt/builder.py` | `systemPrompt.ts`, `context.ts` |
| `utils/abort.py` | `abortController.ts` |

---

*文档生成时间: 2026-04-16*
*分析基于 4 个并行 Agent 的代码对比结果*
