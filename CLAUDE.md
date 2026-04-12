# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此代码库中工作时提供指导。

## 项目概述

明日方舟RAG智能问答助手 - 基于 AgenticRAG 的明日方舟游戏内容问答系统。Agent 驱动架构，DeepSeek-chat Function Calling 自主决定检索路径，支持并行工具调用、SSE 流式输出、GraphRAG 知识图谱、会话管理。**支持用户认证系统**（JWT），用户对话历史持久化到 SQLite。兼容旧版 PipelineRAG（`/query` 端点）。

## 架构

### AgenticRAG（主要流程，`backend/agent/`）

Agent 循环：DeepSeek-chat 自主选择工具 → 并行执行 → 判断信息充足性 → 生成回答

**三个工具：**
1. `arknights_rag_search` - 知识库检索（MultiChannelRetriever → Reranker → ParentDocument）
2. `arknights_graphrag_search` - 知识图谱查询（单实体邻居 / 双实体路径）
3. `web_search` - 网络搜索（Tavily + DuckDuckGo）

**安全机制：** max_rounds=8 硬限制、detect_loop() 循环检测（最近4次相同调用）

### 旧版 PipelineRAG（兼容，`backend/rag/orchestrator.py`）

8步固定流程：查询改写 → 多路召回 → GraphRAG → 重排 → CRAG → Parent Doc → 网络搜索 → 答案生成

### 核心后端组件

**AgenticRAG：**
- `backend/agent/core.py` - Agent 主循环（SSE 流式、并行 FC、循环检测）
- `backend/agent/tools.py` - 工具 Schema 定义 + ToolRegistry
- `backend/agent/tool_implementations.py` - 三个工具的具体实现
- `backend/agent/sessions.py` - 会话管理（TTL、LRU 驱逐、线程安全）
- `backend/agent/prompts.py` - 系统提示词 + 上下文构建

**PipelineRAG：**
- `backend/rag/orchestrator.py` - RAG 流程编排器（单例模式）
- `backend/rag/query_rewriter.py` - 查询改写（fast_rule + Qwen LLM）
- `backend/rag/retrievers.py` - 多路召回（FAISS + BM25 + RRF）
- `backend/rag/crag.py` - CRAG 判断（HIGH/LOW 二分类）
- `backend/rag/answer_generator.py` - 答案生成
- `backend/rag/parent_document.py` - Parent Document 扩展（LRU 缓存）
- `backend/rag/graphrag/builder.py` - 图谱构建（NetworkX DiGraph）
- `backend/rag/graphrag/query.py` - 图谱查询

**基础设施：**
- `backend/storage/__init__.py` - FAISS 向量存储封装
- `backend/api/siliconflow.py` - SiliconFlow API 客户端（嵌入 + 重排 + 网络搜索）
- `backend/api/deepseek.py` - DeepSeek API 客户端（LLM + Function Calling）

### 前端结构
- `frontend/src/views/ChatView.vue` - 问答界面（SSE 流式 + 工具调用卡片）
- `frontend/src/views/AdminView.vue` - 管理面板（调试、评估、参数配置）
- `frontend/src/views/GraphView.vue` - 知识图谱可视化（Cytoscape.js）
- `frontend/src/stores/` - Pinia 状态管理（sessions、settings、quickQuestions）
- `frontend/src/api.js` - API 客户端（含 Agent SSE 流式）

### 数据集合
FAISS 三个 collection：`operators`（干员）、`stories`（剧情）、`knowledge`（游戏知识）

### 知识库切块
- `backend/data/chunker.py` - 文本切块主脚本
- `chunks/knowledge/gameplay_*.md` - 游戏玩法（按 `---` 分隔，每种玩法一个 chunk）

### API 端点

**AgenticRAG：**
- `POST /agent/session` - 创建 Agent 会话
- `POST /agent/chat` - Agent SSE 流式对话
- `GET /agent/session/{id}/messages` - 获取消息历史
- `DELETE /agent/session/{id}` - 删除会话
- `GET /agent/debug/trace` - 调试追踪
- `GET /agent/stats` - 会话统计

**PipelineRAG（兼容）：**
- `POST /query` - 执行完整 RAG 流程
- `POST /debug/step` - 单步执行 RAG 流程（用于调试）

**其他：**
- `GET /chunks/{collection}` - 列出切块文件
- `GET /knowledge-graph` - 获取知识图谱实体关系
- `GET /stats` - 系统统计信息
- `GET /eval/stream` / `POST /eval/start` - 运行 RAG 评估
- `GET /health` - Docker 健康检查
- `GET /operators` / `GET /characters` / `GET /stories` - 数据列表

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `top_k_per_channel` | 8 | 每库召回数量 |
| `rerank_top_k` | 5 | 重排输出数量 |
| `vector_weight` | 0.5 | 向量/BM25 权重 |
| `inner_top_k` | 20 | 内部搜索数量 |

环境变量配置（`backend/.env`）：
- `SILICONFLOW_API_KEY` - 必需，用于嵌入、重排、查询改写
- `DEEPSEEK_API_KEY_2` - 必需，用于 LLM 对话（答案生成）
- `TAVILY_API_KEY` - 可选，用于网络搜索补充

模型配置（`backend/config.py`）：
- 嵌入模型：`BAAI/bge-m3`
- 重排模型：`BAAI/bge-reranker-v2-m3`
- 查询改写：`Qwen/Qwen2.5-7B-Instruct`
- LLM：`deepseek-chat`（DeepSeek API）

## Docker 部署

- `Dockerfile` - 后端镜像构建
- `docker-compose.yml` - 容器编排
- `nginx.conf` - 反向代理配置

## 缓存策略

PipelineRAG 缓存（5 小时 TTL）：
- `_rewrite_cache` - QueryRewriter LLM 结果
- `_recall_cache` - Multi-Channel Recall 结果
- `_hybrid_cache` - Hybrid Search 结果
- `LRUCache` - Parent Document（max 100 条）
- `_bm25_indexes` - BM25 索引（懒加载）

AgenticRAG 会话：
- TTL 3600s，最大 1000 会话，LRU 驱逐最旧会话
- BM25 索引和 GraphBuilder 懒加载单例（线程安全）

## 开发注意事项

- AgenticRAG 使用 DeepSeek-chat Function Calling，**不要传 `parallel_tool_calls` 参数**（会使其更保守）
- Agent 工具通过 `ToolRegistry` 注册，实现在 `tool_implementations.py`
- SSE 事件类型：`tool_calls_start`、`tool_call_result`、`answer_delta`、`answer_done`、`error`
- GraphRAG 使用 `nx.DiGraph`（有向图），路径查找使用无向视图
- 旧版 PipelineRAG 仍可通过 `/query` 端点使用
- BM25 索引采用懒加载策略，首次召回时加载
- FAISS 向量数据持久化到 `faiss_index/` 目录
- GraphRAG 实体关系数据在 `chunks/graphrag/entity_relations.json`

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
