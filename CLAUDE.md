# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此代码库中工作时提供指导。

## 项目概述

明日方舟RAG智能问答助手 - 基于 RAG 的明日方舟游戏内容问答系统。支持多路召回（向量 + BM25）、Cross-Encoder 重排、CRAG 自判断（HIGH/LOW 二分类）、GraphRAG 知识图谱（非流式响应）。

## 架构

### 后端 RAG 流程（8 步，位于 `backend/rag/orchestrator.py`）

1. **查询改写 (Query Rewrite)** - fast_rule 快速匹配 + Qwen LLM 精判
2. **多路召回 (Multi-Channel Recall)** - 并行 BM25 + 向量搜索，RRF 融合（operators/stories/knowledge 三个 collection）
3. **GraphRAG 查询**（与召回并行）- 知识图谱查询（无 LLM，使用 QueryRewriter 传递的参数）
4. **Cross-Encoder 重排** - BAAI/bge-reranker-v2-m3
5. **CRAG 判断** - HIGH/LOW 二分类
6. **Parent Document** - 扩展为完整干员/剧情原文
7. **网络搜索** - CRAG LOW 时 Tavily 补充
8. **答案生成** - DeepSeek 生成最终回答

### 核心后端组件
- `backend/rag/orchestrator.py` - RAG 流程编排器（单例模式）
- `backend/rag/query_rewriter.py` - 查询改写（fast_rule 快速匹配 + Qwen LLM 精判）
- `backend/rag/multi_channel_recall.py` - 多路召回（ThreadPoolExecutor 并发）
- `backend/rag/hybrid_search.py` - 混合搜索（向量 + BM25 + 标准 RRF）
- `backend/rag/reranker.py` - Cross-Encoder 重排（SiliconFlow API）
- `backend/rag/crag.py` - CRAG 判断（HIGH/LOW 二分类）
- `backend/rag/answer_generator.py` - 答案生成（DeepSeek API）
- `backend/rag/parent_document.py` - Parent Document 扩展（LRU 缓存）
- `backend/rag/graphrag/query.py` - 图谱查询（无 LLM）
- `backend/rag/graphrag/builder.py` - 图谱构建（NetworkX）
- `backend/storage/chroma_client.py` - ChromaDB 封装
- `backend/api/siliconflow.py` - SiliconFlow API 客户端（嵌入 + 重排 + 查询改写）
- `backend/api/deepseek.py` - DeepSeek API 客户端（LLM 对话）

### 前端结构
- `frontend/src/views/ChatView.vue` - 问答界面（非流式）
- `frontend/src/views/AdminView.vue` - 管理面板（调试、评估、参数配置）
- `frontend/src/views/GraphView.vue` - 知识图谱可视化（Cytoscape.js）
- `frontend/src/stores/` - Pinia 状态管理（sessions、settings、quickQuestions）
- `frontend/src/composables/useGraphController.js` - 图谱可视化逻辑

### 数据集合
ChromaDB 三个 collection：`operators`（干员）、`stories`（剧情）、`knowledge`（游戏知识）

### 知识库切块
- `backend/data/chunker.py` - 文本切块主脚本
- `chunks/knowledge/gameplay_*.md` - 游戏玩法（按 `---` 分隔，每种玩法一个 chunk）

### API 端点
- `POST /query` - 执行完整 RAG 流程
- `POST /debug/step` - 单步执行 RAG 流程（用于调试）
- `GET /chunks/{collection}` - 列出切块文件
- `GET /graph` - 获取知识图谱实体关系
- `GET /stats` - 系统统计信息
- `GET /eval` - 运行 RAG 评估
- `GET /health` - Docker 健康检查
- `GET /operators` - 干员列表
- `GET /characters` - 角色列表
- `GET /stories` - 故事列表

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

所有缓存均使用 5 小时 TTL：
- `_rewrite_cache` - QueryRewriter LLM 结果
- `_recall_cache` - Multi-Channel Recall 结果
- `_hybrid_cache` - Hybrid Search 结果（key 包含 vector_weight 和 inner_top_k）
- `LRUCache` - Parent Document（max 100 条）
- `_bm25_indexes` - BM25 索引（懒加载）

## 开发注意事项

- 后端使用单例模式管理重量级 RAG 组件（首次请求时初始化）
- BM25 索引采用懒加载策略，首次召回时加载
- QueryRewriter 使用 fast_rule 快速处理常见模式，复杂查询交给 LLM
- 多干员查询、多属性查询、代词查询均交给 LLM 处理
- GraphRAG 使用 QueryRewriter 传递的 is_relation_query 和 detected_operators，无独立 LLM 调用
- CRAG 只使用 HIGH/LOW 二分类，无 MEDIUM/GRAY
- ChromaDB 数据持久化到 `chroma_db/` 目录
- 前端默认非流式输出，AnswerGenerator 无缓存