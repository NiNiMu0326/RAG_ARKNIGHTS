# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此代码库中工作时提供指导。

## 项目概述

明日方舟 Agentic RAG 问答系统。Agent 通过 Function Calling 自主决定检索路径，支持并行工具调用、SSE 流式输出、GraphRAG 知识图谱、Skills 可插拔技能系统、用户认证（JWT）、会话持久化（SQLite）、多 LLM 模型切换。

**注意：本项目已移除旧的 PipelineRAG 架构。所有 RAG 功能通过 Agent 工具调用实现，不存在独立的查询改写/CRAG/答案生成步骤。**

## 架构

### Agent 主循环（`backend/agent/core.py`）

```
用户消息 → build_messages() → LLM(FC) → tool_calls? → 并行执行 → 加入结果 → 继续循环
                                                    ↓ 无 tool_calls
                                              流式输出回答 → 结束
```

**四个工具（`backend/agent/tool_implementations.py`）：**
1. `arknights_rag_search` - 知识库检索（FAISS + BM25 → RRF → 重排 → Parent Doc）
2. `arknights_graphrag_search` - 知识图谱查询（单实体邻居 / 双实体路径）
3. `web_search` - 网络搜索（Tavily + DuckDuckGo）
4. `read_skill` - 读取 `data/skills/` 中的 Markdown 技能文件

**安全机制：** max_rounds=8 硬限制、detect_loop() 循环检测（最近 3 轮相同 tool_calls）

### Skills 系统（`backend/agent/skills.py`）

技能文件位于 `data/skills/`，Markdown 格式，通过 `read_skill` 工具按需加载到 Agent 上下文。`prompts.py` 中的系统提示词会自动列出可用技能清单。

### LLM 多模型（`backend/api/llm_factory.py`）

所有 Provider 通过 OpenAI 兼容 API 统一，底层复用 `DeepSeekClient`（切换 base_url/api_key/model）。

| model_id | Provider | 显示名称 |
|----------|----------|----------|
| `siliconflow-deepseek-v3` | SiliconFlow | DeepSeek-V3.2 (硅基流动) |
| `deepseek-chat` | DeepSeek | DeepSeek-V3.2 (DeepSeek官方) |
| `minimax-m2.5` | MiniMax | MiniMax-M2.5 |
| `minimax-m2.7` | MiniMax | MiniMax-M2.7 |

默认模型：`siliconflow-deepseek-v3`

### 核心后端文件

**Agent 核心：**
- `backend/agent/core.py` - Agent 主循环（SSE、并行 FC、循环检测）
- `backend/agent/tools.py` - 工具 Schema 定义 + ToolRegistry
- `backend/agent/tool_implementations.py` - 四个工具实现 + BM25/GraphBuilder 懒加载单例
- `backend/agent/sessions.py` - 会话管理（TTL 3600s、LRU、线程安全）
- `backend/agent/prompts.py` - 系统提示词 + 上下文构建
- `backend/agent/skills.py` - Skills 扫描、读取、摘要

**API 客户端：**
- `backend/api/llm_factory.py` - 多 Provider LLM 工厂
- `backend/api/deepseek.py` - OpenAI 兼容客户端（LLM + Function Calling + 流式）
- `backend/api/siliconflow.py` - SiliconFlow API（嵌入 + 重排 + 搜索）

**RAG 基础设施（被 Agent 工具调用）：**
- `backend/rag/retrievers.py` - 多通道检索（FAISS + BM25 + RRF），含 5h 缓存
- `backend/rag/parent_document.py` - Parent Document 扩展（LRU 缓存）
- `backend/rag/alias_map.py` - 干员别名映射（供 `/quick-questions` API 使用）
- `backend/rag/graphrag/builder.py` - 图谱构建（NetworkX DiGraph）
- `backend/rag/graphrag/query.py` - 图谱查询（单例 get_graph_builder）

**LangChain 封装（仅检索相关，LLM ChatModel 已删除）：**
- `backend/lc/embeddings.py` - LangChain Embeddings（被 retrievers.py 和 tool_implementations.py 使用）
- `backend/lc/reranker.py` - LangChain Reranker（被 tool_implementations.py 使用）

**基础设施：**
- `backend/storage/faiss_client.py` - FAISS 索引封装
- `backend/db.py` - SQLite 数据库（aiosqlite）
- `backend/auth.py` - JWT 认证

### 前端结构

- `frontend/src/views/ChatView.vue` - 问答界面（SSE 流式 + 工具调用卡片）
- `frontend/src/views/AdminView.vue` - 管理面板（Chunk 可视化、数据仪表板）
- `frontend/src/views/GraphView.vue` - 知识图谱可视化（Cytoscape.js）
- `frontend/src/stores/` - Pinia 状态管理（sessions、auth、settings、quickQuestions）
- `frontend/src/api.js` - API 客户端（Agent SSE）

### API 端点

**Agent：** `POST /agent/chat`、`POST /agent/session`、`GET /agent/models`
**认证：** `POST /auth/register`、`POST /auth/login`、`GET /auth/me`
**会话：** `GET /conversations`、`POST /conversations/sync`、`DELETE /conversations/{id}`
**数据：** `GET /health`、`GET /stats`、`GET /chunks/{collection}`、`GET /knowledge-graph`
**快捷：** `GET /quick-questions`、`GET /operators`、`GET /stories`

完整路由见 `backend/main.py`。

## 环境变量（`backend/.env`）

- `SILICONFLOW_API_KEY` - 必需（嵌入 + 重排 + 搜索）
- `DEEPSEEK_API_KEY_2` - 可选（DeepSeek 官方模型）
- `TAVILY_API_KEY` - 可选（网络搜索补充）
- `MINIMAX_API_KEY` - 可选（MiniMax 模型）

## 开发注意事项

- Agent 使用 DeepSeek Function Calling，**不要传 `parallel_tool_calls` 参数**（会使其更保守）
- Agent 工具通过 `ToolRegistry` 注册，实现在 `tool_implementations.py`
- SSE 事件类型：`thinking_start`、`thinking_delta`、`tool_calls_start`、`tool_executing`、`tool_call_result`、`answer_delta`、`answer_done`、`error`
- GraphRAG 使用 `nx.DiGraph`（有向图），路径查找使用无向视图
- BM25 索引和 GraphBuilder 采用懒加载单例（线程安全）
- FAISS 向量数据持久化到 `faiss_index/` 目录
- GraphRAG 实体关系数据在 `chunks/graphrag/entity_relations.json`
- Skills 文件放在 `data/skills/`，每个技能一个 Markdown 文件

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **RAG_ARKNIGHTS_LangChain** (1972 symbols, 3495 relationships, 56 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/RAG_ARKNIGHTS_LangChain/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/RAG_ARKNIGHTS_LangChain/context` | Codebase overview, check index freshness |
| `gitnexus://repo/RAG_ARKNIGHTS_LangChain/clusters` | All functional areas |
| `gitnexus://repo/RAG_ARKNIGHTS_LangChain/processes` | All execution flows |
| `gitnexus://repo/RAG_ARKNIGHTS_LangChain/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
