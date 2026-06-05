# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此代码库中工作时提供指导。

## 项目概述

明日方舟 ARKNIGHTS Agent 问答系统。一个 AI Agent，通过 Function Calling 自主决定检索路径：知识库检索、知识图谱查询、网络搜索，三个工具可并行调用。支持 SSE 流式输出、用户认证（JWT）、会话持久化（SQLite）、多 LLM 模型切换。

本项目已移除旧的 PipelineRAG 架构，所有 RAG 功能通过 Agent 工具调用实现，不存在独立的查询改写/CRAG/答案生成步骤。

## 服务器

- **地址**：119.147.202.190:14602
- **SSH**：`ssh root@119.147.202.190 -p 14602`
- **密码**：LLll11..
- **项目路径**：服务器上项目位于 `/srv/projects/arknights-rag/`

## 架构

### Agent 主循环（`backend/agent/core.py`）

```
用户消息 → build_messages() → LLM(FC) → tool_calls? → 并行执行 → 结果注入 → 继续循环
                                                    ↓ 无 tool_calls
                                              流式输出回答 → 结束
```

每轮 LLM 返回工具调用时并行执行，结果加入消息历史继续下一轮，直到模型认为信息充足或达到 max_rounds=8 上限。

### 三个工具（`backend/agent/tool_implementations.py`）

| 工具 | 功能 | 流程 |
|------|------|------|
| `arknights_rag_search` | 知识库检索 | FAISS + BM25 → RRF 融合 → Cross-Encoder 重排 → Parent Document 扩展 |
| `arknights_graphrag_search` | 知识图谱查询 | 单实体邻居查询 / 双实体最短路径查找 |
| `web_search` | 网络搜索 | Tavily API + DuckDuckGo 兜底 |

工具通过 `ToolRegistry` 注册，Schema 定义在 `tools.py`，实现在 `tool_implementations.py`。

### 安全机制

- max_rounds=8 硬限制
- `detect_loop()` 循环检测（最近 3 轮相同 tool_calls 即终止）
- LLM 最大输出 token 限制

### LLM 多模型（`backend/api/llm_factory.py`）

所有 Provider 通过 OpenAI 兼容 API 统一，底层复用 `DeepSeekClient`（切换 base_url/api_key/model）。

| model_id | Provider | 显示名称 |
|----------|----------|----------|
| `deepseek-chat` | DeepSeek | DeepSeek-V4-Flash (DeepSeek官方) |
| `minimax-m2.7` | MiniMax | MiniMax-M2.7 |

默认模型：`minimax-m2.7`

### 会话管理（`backend/agent/sessions.py`）

- TTL 3600 秒，最大 1000 会话，LRU 驱逐
- 线程安全（asyncio.Lock）
- 前端 Pinia sessions store 同步管理，支持 localStorage + 服务端双重持久化

## 文件清单

### Agent 核心（`backend/agent/`）

| 文件 | 职责 |
|------|------|
| `core.py` | Agent 主循环：SSE 流式、并行 Function Calling、循环检测、消息构建 |
| `tools.py` | 三个工具的 Schema 定义 + ToolRegistry 注册表 |
| `tool_implementations.py` | 三个工具的实际实现 + BM25/GraphBuilder 懒加载单例 |
| `sessions.py` | 会话管理：创建、查询、TTL 过期、LRU 驱逐、线程安全 |
| `prompts.py` | 系统提示词模板 + build_messages() 消息上下文构建 |

### API 客户端（`backend/api/`）

| 文件 | 职责 |
|------|------|
| `llm_factory.py` | 多 Provider LLM 工厂，模型列表、创建客户端 |
| `deepseek.py` | OpenAI 兼容客户端：Chat Completion + Function Calling + SSE 流式 |
| `siliconflow.py` | SiliconFlow API：嵌入（bge-m3）、重排（bge-reranker-v2-m3）、LLM |
| `web_search.py` | 网络搜索：Tavily API 优先，DuckDuckGo HTML 解析兜底 |

### RAG 基础设施（`backend/rag/`）

| 文件 | 职责 |
|------|------|
| `retrievers.py` | 多通道检索：FAISS 向量 + BM25 关键词 → RRF 融合，结果缓存 5h |
| `parent_document.py` | Parent Document 扩展：检索到的 chunk → 对应父文档，LRU 缓存 max 100 |
| `alias_map.py` | 干员别名映射字典，供 `/quick-questions` API 使用 |
| `graphrag/builder.py` | 知识图谱构建：从 entity_relations.json 构建 NetworkX DiGraph |
| `graphrag/extractor.py` | 实体关系提取 |
| `graphrag/query.py` | 图谱查询单例（get_graph_builder）：邻居查询 + 最短路径查找 |

### LangChain 封装（`backend/lc/`）

| 文件 | 职责 |
|------|------|
| `embeddings.py` | LangChain Embeddings 封装，被 retrievers.py 和 tool_implementations.py 使用 |
| `reranker.py` | LangChain Cross-Encoder Reranker 封装，被 tool_implementations.py 使用 |

### 基础设施（`backend/`）

| 文件 | 职责 |
|------|------|
| `main.py` | FastAPI 主应用：所有路由、SSE 端点、CORS、静态文件挂载 |
| `config.py` | 全局配置：API Keys、模型参数、路径常量 |
| `db.py` | SQLite 数据库（aiosqlite）：用户表、会话表初始化 |
| `auth.py` | JWT 认证：注册、登录、token 签发/验证、密码哈希 |
| `storage/faiss_client.py` | FAISS 向量索引封装：加载、搜索、持久化到 `faiss_index/` |

### 数据脚本（`backend/data/`）

| 文件 | 职责 |
|------|------|
| `chunker.py` | 文本切块：将原始数据切成检索用 chunk |
| `bm25_index.py` | BM25 关键词索引构建 |

### 前端（`frontend/src/`）

**页面（views/）：**
| 文件 | 路由 | 功能 |
|------|------|------|
| `ChatView.vue` | `/chat` | 问答界面：SSE 流式对话、工具调用卡片、思考过程展开、快捷问题按钮、消息队列 |
| `AdminView.vue` | `/admin` | 管理面板：Chunk 浏览器（按集合浏览/搜索切块）、数据仪表板（统计图表） |
| `GraphView.vue` | `/graph` | 交互式知识图谱：Cytoscape.js 力导向布局、节点搜索、邻居展开、关系筛选 |

**组件（components/）：**
| 文件 | 功能 |
|------|------|
| `AppSidebar.vue` | 侧边栏：导航 + 会话列表管理 + 图谱控制面板（搜索、选择、关系筛选） |
| `AppHeader.vue` | 顶部栏：移动端菜单按钮 + 页面标题 + 设置入口 |
| `AuthModal.vue` | 登录/注册弹窗 |
| `SettingsModal.vue` | 设置弹窗：账户信息/修改密码、主题切换、模型选择、关于 |
| `Toast.vue` | 全局通知提示 |

**状态管理（stores/）：**
| 文件 | 职责 |
|------|------|
| `sessions.js` | 会话 CRUD、消息管理、localStorage/服务端同步 |
| `auth.js` | JWT token 管理、用户状态、登录/注册/登出 |
| `settings.js` | 主题切换、模型选择、设置持久化 |
| `quickQuestions.js` | 快捷问题缓存 |
| `toast.js` | 通知消息 |

**其他：**
| 文件 | 职责 |
|------|------|
| `api.js` | API 客户端：所有后端接口封装，含 `agentChat()` SSE 流式调用 |
| `composables/useGraphController.js` | 图谱控制器单例，GraphView 和 AppSidebar 共享 |
| `assets/styles.css` | 全局样式（CSS 变量、双主题、组件样式） |
| `assets/graphrag.css` | 知识图谱专用样式 |

### 数据目录

| 路径 | 内容 |
|------|------|
| `data/` | 原始数据集（JSON/Markdown）：干员数据、故事、知识等 |
| `chunks/` | 文本切块输出，按 collection 分目录 |
| `chunks/graphrag/entity_relations.json` | 知识图谱实体关系数据 |
| `faiss_index/` | FAISS 向量索引持久化文件 |

## API 端点

### Agent
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/agent/chat` | Agent SSE 流式对话（核心端点） |
| POST | `/agent/session` | 创建会话，返回 session_id |
| GET | `/agent/session/{id}/messages` | 获取会话消息历史 |
| DELETE | `/agent/session/{id}` | 删除会话 |
| GET | `/agent/models` | 可用 LLM 模型列表 |
| GET | `/agent/stats` | 会话统计 |

### 认证
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/auth/register` | 注册（username, account, password） |
| POST | `/auth/login` | 登录（account, password），返回 JWT token |
| GET | `/auth/me` | 当前用户信息 |
| POST | `/auth/change-password` | 修改密码 |

### 会话管理
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/conversations` | 用户会话列表 |
| GET | `/conversations/{id}/messages` | 会话消息 |
| POST | `/conversations/sync` | 同步本地会话到服务端 |
| DELETE | `/conversations/{id}` | 删除会话 |
| PUT | `/conversations/{id}/rename` | 重命名会话 |

### 数据
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/status` | 配置状态（模型、API 可用性） |
| GET | `/stats` | 数据统计（干员数、故事数、知识数、图谱节点/边数） |
| GET | `/chunks/{collection}` | 指定集合的切块列表 |
| GET | `/chunks/{collection}/{id}` | 单个切块详情 |
| GET | `/knowledge-graph` | 知识图谱完整数据（entities + relations） |
| GET | `/quick-questions` | 快捷问题列表 |
| GET | `/operators` | 干员列表 |
| GET | `/characters` | 角色列表 |
| GET | `/stories` | 故事列表 |

完整路由定义见 `backend/main.py`。

## 环境变量（`backend/.env`）

| 变量 | 必须 | 说明 |
|------|------|------|
| `SILICONFLOW_API_KEY` | 是 | 嵌入（bge-m3）+ 重排（bge-reranker-v2-m3）+ 默认 LLM |
| `JWT_SECRET` | 是 | JWT 签名密钥，不设置则服务拒绝启动 |
| `DEEPSEEK_API_KEY_2` | 否 | DeepSeek 官方模型 API Key |
| `TAVILY_API_KEY` | 否 | Tavily 网络搜索，不填则 DuckDuckGo 兜底 |
| `MINIMAX_API_KEY` | 否 | MiniMax M2.7 模型 |
| `PORT` | 否 | 后端端口，默认 8100 |

## 开发注意事项

- **端口**：后端 8100，前端开发服务器 5300（Vite 代理转发 API 到 8100）
- Agent 使用 DeepSeek Function Calling，**不要传 `parallel_tool_calls` 参数**（会使其更保守）
- GraphRAG 使用 `nx.DiGraph`（有向图），但路径查找时转为无向视图
- BM25 索引和 GraphBuilder 采用懒加载单例模式（线程安全）
- FAISS 向量数据持久化到 `faiss_index/` 目录
- GraphRAG 实体关系数据在 `chunks/graphrag/entity_relations.json`
- 前端 Vite 代理配置将所有 `/agent`、`/auth`、`/conversations` 等路径转发到后端

### SSE 事件类型

Agent 流式对话使用以下 SSE 事件，按时间顺序：

| 事件 | 含义 |
|------|------|
| `thinking_start` | 开始新一轮思考 |
| `thinking_delta` | 思考过程增量文本 |
| `tool_calls_start` | 模型决定调用工具 |
| `tool_executing` | 正在执行某个工具（含工具名和参数） |
| `tool_call_result` | 工具执行完成（含返回结果） |
| `answer_delta` | 最终回答流式增量 |
| `answer_done` | 回答完成（含总轮数、耗时） |
| `error` | 出错 |

### 技术栈

| 组件 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| Agent LLM | DeepSeek-V4-Flash / MiniMax-M2.7 |
| 向量数据库 | FAISS（内存索引 + 磁盘持久化） |
| 嵌入模型 | BAAI/bge-m3（SiliconFlow API） |
| 重排模型 | BAAI/bge-reranker-v2-m3（SiliconFlow API） |
| 网络搜索 | Tavily API + DuckDuckGo |
| 知识图谱 | NetworkX DiGraph |
| 数据库 | SQLite（aiosqlite 异步） |
| 前端框架 | Vue 3（Composition API + script setup） |
| 状态管理 | Pinia |
| 构建工具 | Vite 5 |
| 图谱可视化 | Cytoscape.js |

### 启动命令

```bash
# 后端
cd backend && uvicorn main:app --host 0.0.0.0 --port 8100

# 前端开发
cd frontend && npm run dev

# 构建索引（首次使用）
python backend/data/chunker.py
python backend/data/bm25_index.py
python backend/build_faiss_index.py
```
## 部署工作流

本项目采用 **本地开发 → Git 推送 → 服务器拉取** 的工作流：

1. **本地开发**：在本地 `D:\Agent\ARKNIGHTSAgent` 修改代码
2. **Git 提交推送**：使用 `git add` + `git commit` + `git push` 推送到远程仓库
3. **服务器部署**：SSH 登录服务器执行 `git pull` 拉取最新代码

### 服务器信息
- **地址**：119.147.202.190:14602
- **SSH**：`ssh root@119.147.202.190 -p 14602`
- **密码**：LLll11..
- **项目路径**：`/srv/projects/arknights-rag/`

### 部署命令示例

```bash
# 本地提交并推送
git add -A
git commit -m "[feat] 描述改动内容"
git push origin main

# 服务器拉取更新
ssh root@119.147.202.190 -p 14602
cd /srv/projects/arknights-rag/
git pull
```

### 注意事项
- 每次重要改动后必须 commit，commit message 使用中文描述
- 推送到仓库后提醒用户到服务器执行 `git pull`
- 服务器上可能需要重启服务才能生效（如 uvicorn）


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
