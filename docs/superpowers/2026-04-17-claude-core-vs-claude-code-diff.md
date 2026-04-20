# Claude Core vs Claude Code 模块差异对比（更新版）

**日期**: 2026-04-17  
**范围**: `/claude-core` (Python) 对比 `/claude-code` (TypeScript)  
**方法**: 基于当前仓库源码静态核对 + 可运行性验证（导入、工具、测试）

---

## 1. 结论摘要

- `claude-core` 已从“最小可跑”进入“稳定最小闭环”阶段。
- 已完成首批阻断性修复：`AgentTool` 导入、`asyncio.race`、`fallback_model`、`max_turns`、README 结构偏差。
- 已落地首批能力补齐：权限系统最小版、MCP 最小闭环、Task 持久化。
- 与 `claude-code` 相比，当前最大的剩余差距集中在 provider 深度能力、完整权限交互、MCP 深度集成、命令与 feature gate 生态。

---

## 2. 模块级对比（逐项）

### 2.1 API / Provider 层

**TypeScript (`claude-code`)**
- 多 Provider：`firstParty/bedrock/vertex/foundry/openai/gemini/grok`
- 有 provider 适配层、模型映射、provider-specific 配置与错误处理

**Python (`claude-core`)**
- 已抽出 provider 适配层，当前支持 `openai` / `gemini`
- 支持基础重试、HTTP 错误映射

**当前差距**
- provider 数量和深度仍远弱于 TS
- 缺 provider-specific 认证与能力矩阵
- 缺 TS 级别的细粒度错误语义与观测集成

### 2.2 Query Engine / Query Loop

**TypeScript**
- 完整 query 编排：多策略压缩、hooks、feature gates、复杂恢复路径

**Python**
- 已实现主循环：流式输出、工具调用、压缩触发、错误处理基础分支
- 已支持 `max_turns`、abort、budget 基础逻辑
- `fallback_model` 已实际生效

**当前差距**
- 缺 hooks 体系与 feature-gated 策略编排
- 缺 TS 级别恢复链路和策略组合
- 缺更细的请求策略、回退策略和上下文治理

### 2.3 Tool 协议与执行器

**TypeScript**
- 完整 Tool 生命周期：输入校验、权限判定、UI 交互、并发与中断策略、MCP 工具池融合

**Python**
- 有 Tool 协议、`validate_input` / `check_permissions` hook
- `StreamingToolExecutor` 已支持稳定并发等待
- 已支持 alias 匹配、统一权限前置判定、`updated_input` 透传、`ask/deny` 基础处理

**当前差距**
- 权限体系已有最小落地，但仍缺 TS 的规则解析、交互确认、permission mode
- 缺 MCP 工具池动态融合能力
- 缺 TS 级别进度事件、UI 交互与更复杂的并发/取消治理

### 2.4 内置工具（Builtin Tools）

**TypeScript**
- `packages/builtin-tools/src/tools` 下约 59 个工具目录（含 feature-gated 工具）

**Python**
- 当前已包含 `file_read/file_write/file_edit/bash/glob/grep/task/agent/mcp`
- `Task` 已支持 JSON 文件持久化
- `MCP` 已支持资源列举与读取

**当前差距**
- 数量与能力跨度仍显著不足
- 文件工具缺关键生产特性（原子写、缓存、IDE/LSP 协同、多媒体文件处理）
- Task 仍缺更强存储抽象与后台治理
- AgentTool 可导入，但整体 agent 编排能力仍显著弱于 TS

### 2.5 Agent 系统

**TypeScript**
- 支持 coordinator/swarms/fork/worktree/复杂会话与权限上下文传播

**Python**
- `WorkerAgent` 已接入 QueryEngine，非纯占位
- 已补齐任务状态基础类型，AgentTool 可完成最小依赖导入

**当前差距**
- 缺完整任务与后台控制基础设施
- Mailbox 仍是简化实现（未按 recipient 精准分发）
- 缺 TS 级别多 agent 编排与运行时治理

### 2.6 Prompt / Context

**TypeScript**
- 动态系统提示构建 + 丰富上下文压缩策略 + 大量 gate 控制

**Python**
- 已有 prompt priority builder
- 已有 `CLAUDE.md` 发现和 git context 构建
- 有 Snip/Auto/Reactive 的基础压缩实现

**当前差距**
- token 估算仍为 `len(text)//4` 级别简化
- 压缩策略深度、稳定性、可观测性显著弱于 TS

### 2.7 MCP / 命令层 / Feature Flags

**TypeScript**
- 丰富命令面与 feature gate 体系，MCP 相关工具完整接入

**Python**
- 已有 `mcp/` 目录、最小 `MCPClient` 与资源读/list 工具
- 仍无对应规模的命令层与 gate 系统

**当前差距**
- MCP 仍是资源级最小实现，缺 tool call、server lifecycle、动态注入
- 缺命令面与运行模式生态
- 缺 feature flag 与 permission mode 能力

---

## 3. 已修复项（2026-04-17 当前状态）

### 已闭环的阻断项
- `AgentTool` 导入问题已修复：补齐 `claude_core.tasks`
- `StreamingToolExecutor` 的 `asyncio.race` 已替换并补测试
- `fallback_model` 已实际生效
- `max_turns` off-by-one 已修复
- README 已与当前源码结构同步

### 已落地的能力补齐
- 工具权限系统最小版已接入 `Bash/File*/Glob/Grep/MCP`
- `StreamingToolExecutor` 已支持权限 `updated_input` 与 `ask/deny` 处理
- MCP 最小闭环已完成：`MCPClient` + `ListMcpResources` + `ReadMcpResource`
- Task 工具已支持 JSON 文件持久化
- Provider 最小抽象已完成：`openai` / `gemini`

---

## 4. 能力完成度（保守估计）

- **核心链路（稳定可跑）**: 65-75%
- **工具系统（生产级）**: 35-45%
- **Agent 编排**: 25-35%
- **Provider/平台适配**: 30-40%
- **命令与特性生态**: 10-20%

> 注: 上述为工程视角估计，不代表 API 覆盖率统计值。

---

## 5. 对旧差距文档的修正说明

以下结论已过期或需修正：

- “`query()` 仍是占位 / 循环缺失” -> **已过期**，当前实现存在完整循环。
- “Prompt manager 不具备优先级/CLAUDE.md/git context” -> **已过期**，当前已具备基础版本。
- “Agent 仅占位” -> **部分过期**，`WorkerAgent` 已有真实 query 调用链路，AgentTool 也已可导入，但 runtime 仍不完整。
- “无 MCP 目录 / 无 MCP 能力” -> **已过期**，当前已具备最小 MCP 资源能力。

---

## 6. 建议下一步

- 第一优先级：补 provider 深度能力（更多 provider、认证链路、provider-specific 语义）
- 第二优先级：补完整权限模式（规则解析、ask 流程、permission mode）
- 第三优先级：扩展 MCP 到 tool call / server lifecycle / 动态工具融合

详见修复计划文档：  
`docs/superpowers/plans/2026-04-17-claude-core-remediation-plan.md`
