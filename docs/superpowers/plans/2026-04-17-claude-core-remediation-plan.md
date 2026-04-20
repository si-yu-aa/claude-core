# Claude Core 详细修复计划（2026-04-17）

**目标**: 将 `claude-core` 从“可跑原型”提升为“稳定可扩展实现”，优先修复可用性问题，再补齐核心能力。  
**基线文档**: `docs/superpowers/2026-04-17-claude-core-vs-claude-code-diff.md`

**状态更新（2026-04-17）**
- P0: 已完成
- P1: 已完成
- P2: 已完成 4/4（权限系统最小版、MCP 最小闭环、Task 持久化、多 Provider 最小抽象）
- 当前剩余最高优先级: provider 深度能力与权限/MCP 进一步扩展

---

## 1. 修复策略与优先级

### P0（立即处理，阻断可用性）
1. 修复 `AgentTool` 导入失败（缺 `claude_core.tasks`）
2. 修复 `StreamingToolExecutor` 的 `asyncio.race` 运行时错误

### P1（核心正确性与稳定性）
1. 修复 fallback model 逻辑失效
2. 修复 `max_turns` off-by-one
3. 修复/同步 README 与真实代码结构
4. 增强关键路径测试覆盖

### P2（能力补齐与架构升级）
1. 工具权限系统落地（非接口化）
2. MCP 最小闭环
3. Task 持久化
4. 多 Provider 能力抽象（先 OpenAI + 1 个目标 provider）

---

## 2. 分阶段执行计划

## Phase 0: 基线与护栏（0.5 天）

**状态**: 已完成

### 目标
- 建立可回归的最小测试护栏，确保后续修复可验证。

### 已完成内容
1. 增加 smoke/import 测试
2. 补充执行器并发等待测试
3. 增加 `max_turns` 边界测试与 fallback 行为测试

### 验收结果
- 关键模块 import 全通过
- 新增测试已稳定保护 P0/P1 缺陷

---

## Phase 1: P0 可用性修复（1-2 天）

**状态**: 已完成

### 1.1 AgentTool 依赖补齐

**完成情况**
1. 新增 `src/claude_core/tasks/`
2. 在 `types.py` 补齐最小兼容结构
3. 保证与 `agent.py` 当前调用字段兼容

**验收结果**
- `import claude_core.tools.builtin.agent` 成功
- `create_agent_tool()` 可实例化

### 1.2 `asyncio.race` 替换

**完成情况**
1. 改用 `asyncio.wait(..., FIRST_COMPLETED)`
2. 修正 future/task 生命周期
3. 保留 progress 唤醒语义

**验收结果**
- 并发/串行执行路径稳定
- 执行器相关测试通过

---

## Phase 2: P1 正确性修复（1-2 天）

**状态**: 已完成

### 2.1 fallback model 生效

**完成情况**
1. 修改 `call_model(...)`，显式接受 `model`
2. query loop 调用传入 `current_model`
3. 配置侧增加 `fallback_model`

**验收结果**
- 主模型失败后请求体中的 `model` 可切换到 fallback

### 2.2 `max_turns` off-by-one

**完成情况**
1. `turn_count` 初始改为 `0`
2. 边界判断与测试同步修正

**验收结果**
- `max_turns=1` 可正常执行首轮再停止

### 2.3 README 对齐

**完成情况**
1. 修正文档结构图
2. 补充 `fallback_model`
3. 同步 `mcp/`、`tasks/` 等真实结构

**验收结果**
- README 中路径可在仓库中一一对应

---

## Phase 3: P2 能力补齐（3-6 天）

**状态**: 进行中（已完成 3/4）

### 3.1 工具权限系统从“接口”到“可用”

**状态**: 已完成（最小版）

**完成情况**
1. 定义权限规则结构（deny/always_allow）
2. 在 `StreamingToolExecutor` 统一执行前判定
3. 为 `File*`、`Bash`、`Glob`、`Grep`、`MCP` 工具提供默认规则实现
4. 支持 `updated_input` 透传与 `ask/deny` 基础处理

**验收结果**
- 可按规则拒绝高风险调用
- 拒绝路径返回一致化错误消息

### 3.2 MCP 最小闭环

**状态**: 已完成

**完成情况**
1. 新增 `src/claude_core/mcp/`（client + types）
2. 在 `ToolUseContextOptions` 接入 `mcp_clients`
3. 增加 `ListMcpResources` / `ReadMcpResource`

**验收结果**
- 能在 mock client 上完成资源列举与读取链路

### 3.3 Task 持久化

**状态**: 已完成（JSON 文件存储）

**完成情况**
1. `tools/builtin/task.py` 从内存存储升级到 JSON 文件存储
2. 支持 `task_store_path`

**验收结果**
- 重启工具实例后任务仍可查询

### 3.4 多 Provider 抽象（第一步）

**状态**: 已完成（最小版）

**目标**
- 在不大改架构的前提下，形成 provider 接口层。

**完成情况**
1. 抽出 provider adapter 层
2. 保留 OpenAI 为默认实现
3. 增加 `gemini` 适配样例
4. `LLMClient` / `query_loop` / `QueryEngineConfig` 接入 provider

**验收结果**
- 可通过配置切换 provider
- `provider=openai/gemini` 的请求构造都有自动化测试覆盖

---

## 3. 文件级改动清单

### 已新增 / 已修改（截至 2026-04-17）
- `src/claude_core/tasks/__init__.py`
- `src/claude_core/tasks/types.py`
- `src/claude_core/mcp/*`
- `src/claude_core/tools/builtin/mcp.py`
- `src/claude_core/tools/permissions.py`
- `src/claude_core/context/project.py`
- `src/claude_core/tools/streaming_executor.py`
- `src/claude_core/engine/query_loop.py`
- `src/claude_core/engine/types.py`
- `src/claude_core/engine/config.py`
- `src/claude_core/tools/builtin/task.py`
- `src/claude_core/tools/builtin/bash.py`
- `README.md`
- `tests/*`（新增多组回归测试）

### 下一阶段预计新增
- `src/claude_core/api/providers/*` 或等价 provider 抽象层
- `src/claude_core/api/factories.py` 或等价 client factory
- provider 相关配置与测试文件

---

## 4. 测试计划

### 已完成
- `StreamingToolExecutor` 并发、等待、权限透传、alias 匹配
- `query_loop` 的 fallback、max_turns、error recovery 边界
- `BashTool` 的 timeout 与 abort
- MCP 资源 list/read
- Task 持久化

### 下一阶段补充
- 更多 provider 适配
- provider-specific 认证与请求语义测试

---

## 5. 风险与回滚

### 当前主要风险
1. 多 Provider 抽象可能带来 client 生命周期变化
2. 权限系统后续扩展到交互式 ask 时，现有最小模型需要演进
3. MCP 从资源级扩展到 tool call 时会引入更多上下文耦合

### 控制措施
1. 保持 provider 抽象与 query loop 解耦
2. 继续先补测试再改逻辑
3. 每个阶段小步提交，可单独回滚

---

## 6. 交付里程碑

### M1
- P0 全部完成
- `claude-core` 关键模块可导入、AgentTool 可运行、执行器无 `race` 错误

### M2
- P1 全部完成
- fallback 与 max_turns 行为正确
- README 与实现对齐

### M3
- P2 首批能力完成（权限系统最小版 + MCP 最小闭环 + Task 持久化）

### M4（下一阶段）
- provider 深度能力落地
- 至少再增加一个非当前 provider 的适配样例或认证链路

---

## 7. Definition of Done

### 当前阶段已达成
1. P0/P1 项目全部闭环并有自动化测试覆盖
2. 文档与实现一致，不再出现结构性误导
3. `claude-core` 在“无特性开关依赖”的条件下稳定运行核心链路
4. P2 首批能力已完成并可演示（权限系统最小版 + MCP 最小闭环 + Task 持久化）

### 下一阶段 Done 标准
1. provider 深度能力进入主链路
2. provider-specific 认证/语义有自动化测试覆盖
3. 权限与 MCP 下一阶段能力继续闭环
