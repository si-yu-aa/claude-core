# Code Reading Documentation Library Design

**Date:** 2026-04-17

**Goal:** Generate linear call-chain documentation for claude-core Python SDK

---

## 1. Overview

A linear documentation library that guides readers through the claude-core codebase from SDK entry point, following the actual call sequence. Each module document explains responsibilities, interfaces, callers, callees, key logic, and includes a Mermaid diagram.

**Target reader:** Single user (project owner), sequential reading from entry point.

---

## 2. Document Structure

```
docs/code-reading/
  01-sdk-entry.md        # SDK entry, exposed APIs
  02-query-engine.md      # QueryEngine orchestration layer
  03-query-loop.md        # Core query loop
  04-tool-system.md       # Tool protocol and StreamingToolExecutor
  05-builtin-tools.md     # Built-in tools (FileRead/Write/Edit/Bash/Task/Glob/Grep)
  06-context.md          # Context Manager and compression strategies
  07-agents.md           # Agent system (WorkerAgent/ForkContext)
  08-prompt.md           # Prompt builder (6-level priority/CLAUDE.md/Git)
  09-api-client.md       # API client (retry/error handling)
  10-mcp.md              # MCP client
  11-langfuse.md         # Distributed tracing
  index.md               # Index + call relationship Mermaid diagram
```

---

## 3. Per-Module Document Template

Each module document contains:

1. **Module Responsibility** — What this module does (1-2 sentences)
2. **Core Interfaces** — Public classes and functions
3. **Called By** — Who calls this module
4. **Calls To** — What this module calls
5. **Key Logic** — Main execution flow (3-5 steps)
6. **Mermaid Diagram** — Call relationship diagram

**Format:** ~20-30 lines per module, no code snippets

---

## 4. Complete Call Chain

```
SDK Entry (claude_core.SDK)
  ↓
QueryEngine.submit_message()
  ↓
QueryLoop.query()
  ├→ call_model() → API Client
  ├→ StreamingToolExecutor → Tool.call()
  │   └→ Builtin Tools (FileRead/Write/Edit/Bash/...)
  └→ Context Manager (compression/budget)
      ↓
    Agent (WorkerAgent)
      ↓
    Prompt Builder
```

---

## 5. Module Summary

| Module | File | Responsibility |
|--------|------|----------------|
| SDK Entry | `__init__.py`, `engine/query_engine.py` | Expose SDK, orchestrate messages |
| Query Engine | `engine/query_engine.py` | High-level query orchestration |
| Query Loop | `engine/query_loop.py` | Core async generator loop |
| Tool System | `tools/base.py`, `tools/streaming_executor.py` | Tool protocol, concurrent execution |
| Builtin Tools | `tools/builtin/*.py` | FileRead, FileWrite, FileEdit, Bash, Task, Glob, Grep |
| Context | `context/manager.py`, `context/compression.py` | Token budget, context compression |
| Agents | `agents/worker.py`, `agents/types.py` | WorkerAgent, ForkContext, pause/resume |
| Prompt | `prompt/builder.py`, `prompt/manager.py` | 6-level priority, CLAUDE.md, git context |
| API Client | `api/client.py`, `api/errors.py` | OpenAI-compatible client, retry, error mapping |
| MCP | `mcp/client.py`, `mcp/tool.py` | MCP server connection, JSON-RPC 2.0 |
| Langfuse | `langfuse/client.py`, `langfuse/tracer.py` | Distributed tracing |

---

## 6. Generation Approach

- Use parallel agents to generate each module document
- Each agent reads source code and generates content per template
- Final index.md generated after all modules complete

---

## 7. Not in Scope

- API reference documentation (docstrings)
- Test documentation
- Deployment/configuration docs
