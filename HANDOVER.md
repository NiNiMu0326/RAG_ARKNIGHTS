# HANDOVER.md - 项目交接文档

> 最后更新：2026-04-13

## 一、已实现功能

### 核心架构
- [x] **AgenticRAG Agent 循环** — DeepSeek-chat Function Calling 自主决定检索路径
- [x] **并行工具调用** — Agent 可同时发起多个无依赖的工具调用
- [x] **循环检测** — 最近4次相同调用时自动终止，防止死循环
- [x] **SSE 流式输出** — 实时返回 thinking_delta、tool_executing、answer_delta 等事件
- [x] **ToolRegistry** — 工具注册中心，统一管理工具 Schema 和实现

### 四个工具
- [x] **arknights_rag_search** — FAISS 向量 + BM25 混合检索 + Cross-Encoder 重排 + Parent Document
- [x] **arknights_graphrag_search** — NetworkX 知识图谱（单实体邻居 / 双实体路径）
- [x] **web_search** — Tavily + DuckDuckGo 网络搜索
- [x] **read_skill** — 读取游戏资料技能（Skills 系统）

### Skills 系统
- [x] **技能模块管理** — `backend/agent/skills.py`，技能文件位于 `data/skills/`
- [x] **按需加载** — Agent 通过 `read_skill` 工具请求时才加载到上下文
- [x] **Markdown 格式** — 每个技能一个 `.md` 文件

### 用户认证与会话
- [x] **JWT 认证** — 注册、登录、密码修改、token 验证
- [x] **SQLite 持久化** — 用户对话历史存储到 `data/arknights_rag.db`
- [x] **会话管理** — TTL 3600s、最大 1000 会话、LRU 驱逐
- [x] **多 LLM 支持** — DeepSeek / SiliconFlow Pro / MiniMax 模型切换

### 前端
- [x] **ChatView** — SSE 流式问答界面，工具调用卡片展示
- [x] **AdminView** — Chunk 可视化、数据仪表板
- [x] **GraphView** — Cytoscape.js 知识图谱可视化
- [x] **设置面板** — 模型选择、参数配置
- [x] **多会话管理** — 会话列表、创建、删除、重命名

### 基础设施
- [x] **Docker 部署** — Dockerfile + docker-compose + nginx 反向代理
- [x] **systemd 服务** — `arknights-rag.service`

### PipelineRAG 彻底清理（本次完成）
- [x] 删除 `backend/rag/query_rewriter.py` — PipelineRAG 查询改写（无任何活跃 import）
- [x] 删除 `backend/rag/crag.py` — PipelineRAG CRAG 判断（无任何活跃 import）
- [x] 删除 `backend/rag/answer_generator.py` — PipelineRAG 答案生成（无任何活跃 import）
- [x] 删除 `backend/lc/llm.py` — LangChain ChatModel 封装（Agent 直接用 deepseek.py）
- [x] 删除 `backend/config.py` 中 `LLM_MODEL`（Qwen 查询改写用）和 `CRAG_*` 阈值常量
- [x] 修复 `backend/main.py` 中 `LLM_MODEL` 引用 → `config.DEEPSEEK_LLM_MODEL`
- [x] 重写 README.md — 删除所有 PipelineRAG/Qwen/CRAG/QueryRewriter 残留描述
- [x] 重写 CLAUDE.md — 删除所有 PipelineRAG 残留，明确标注"已移除 PipelineRAG"

### 代码清理（前期完成）
- [x] 删除 `backend/config.py` 中 `EVAL_QUESTIONS_FILE` 残留常量
- [x] 删除 `frontend/src/api.js` 中 `api.query()` 和 `api.runEval()` 死代码
- [x] 删除 `frontend/vite.config.js` 中 `/query`、`/debug`、`/eval` 无效代理
- [x] 删除 `AdminView.vue` 评估面板（后端已无 eval 端点）
- [x] 删除 `frontend/src/utils/quickQuestions.js`（已被后端替代）
- [x] 清理 `frontend/src/stores/quickQuestions.js` 冗余方法
- [x] 修正 `arknights-rag.service` WorkingDirectory 路径
- [x] 修正 Dockerfile Python 版本 3.10 → 3.11

---

## 二、待实现

### 1. run_command 工具
让 Agent 可以调用命令行执行操作。
- 需要人工审批机制（安全考虑）
- 白名单命令限制
- 超时和输出截断

### 2. 上下文管理模块
管理 Agent 的长对话上下文。
- 对话历史摘要/压缩
- 滑动窗口策略
- 重要信息提取和保留

---

## 三、待改进

### 架构演进
- 项目方向从 RAG Agent 向通用 Agent 演进，RAG 逐渐降级为一个 Skill
- 未来考虑将 `arknights_rag_search` 和 `arknights_graphrag_search` 合并为统一的 RAG Skill
- `run_command` 实现后需重新设计 Skills 加载机制，支持动态技能注册

### 测试
- 前端未做单元测试 / E2E 测试
- 后端 `tests/` 目录下测试覆盖不完整
- 错误处理（特别是网络超时、API 限额）可进一步细化
