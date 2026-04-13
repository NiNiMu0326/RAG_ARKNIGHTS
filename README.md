# 明日方舟 Agentic RAG

基于明日方舟数据集的 Agentic RAG 智能问答系统。Agent 通过 Function Calling 自主决定检索路径，支持知识库检索、知识图谱查询和网络搜索。

## 功能特性

- **Agentic RAG**：LLM 通过 Function Calling 自主选择工具、并行执行、判断信息充足性
- **多 LLM 支持**：DeepSeek-V3.2（硅基流动/官方）、MiniMax-M2.5/M2.7 多模型切换
- **用户认证**：注册、登录、JWT 令牌认证，会话持久化到 SQLite
- **SSE 流式输出**：实时显示 Agent 思考过程、工具执行状态、回答生成
- **知识库检索**：FAISS 向量 + BM25 混合检索 + Cross-Encoder 重排 + Parent Document 扩展
- **GraphRAG**：NetworkX 知识图谱，支持单实体邻居查询和双实体关系路径查找
- **网络搜索**：Tavily + DuckDuckGo 补充外部信息

## 系统要求

- **Python**：3.11+
- **Node.js**：18+（前端构建）
- **内存**：至少 8 GB RAM（推荐 16 GB）

## 快速开始

### 1. 克隆代码

```bash
git clone https://github.com/NiNiMu0326/RAG_ARKNIGHTS_Agent.git
cd RAG_ARKNIGHTS_Agent
```

### 2. 后端

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入 API Key
```

必需环境变量：
- `SILICONFLOW_API_KEY` - 向量嵌入 + 重排（[siliconflow.cn](https://siliconflow.cn)）

可选：
- `DEEPSEEK_API_KEY_2` - DeepSeek 官方模型（不填则默认使用硅基流动）
- `TAVILY_API_KEY` - 网络搜索（不填则使用 DuckDuckGo 兜底）
- `MINIMAX_API_KEY` - MiniMax 模型

### 3. 前端

```bash
cd frontend
npm install
```

### 4. 构建索引

```bash
python backend/data/chunker.py           # 文本切块
python backend/data/bm25_index.py        # BM25 索引
python backend/build_faiss_index.py      # FAISS 向量索引
```

### 5. 启动

```bash
# 后端
cd backend && uvicorn main:app --host 0.0.0.0 --port 8889

# 前端开发
cd frontend && npm run dev
```

访问 http://localhost:5175

## Agent 工作流

```
用户提问 → LLM Function Calling → 工具选择 → 并行执行 → 信息充足？ → 生成回答
                                    ↓ 否
                              补充检索（最多 8 轮）
```

**三个工具：**

| 工具 | 功能 | 内部流程 |
|------|------|----------|
| `arknights_rag_search` | 知识库检索 | FAISS + BM25 → RRF 融合 → 重排 → Parent Doc |
| `arknights_graphrag_search` | 知识图谱查询 | 单实体邻居 / 双实体最短路径 |
| `web_search` | 网络搜索 | Tavily + DuckDuckGo |

**安全机制：** 最大 8 轮调用、循环检测（最近 3 轮相同 tool_calls）、SSE 流式输出

## 项目结构

```
RAG_ARKNIGHTS_Agent/
├── backend/
│   ├── main.py              # FastAPI 主应用（所有路由）
│   ├── config.py            # 配置（API Keys、模型参数、路径）
│   ├── requirements.txt
│   ├── agent/               # Agent 核心
│   │   ├── core.py          # Agent 主循环（SSE、并行 FC、循环检测）
│   │   ├── tools.py         # 工具 Schema + ToolRegistry
│   │   ├── tool_implementations.py  # 工具实现（RAG/GraphRAG/Web）
│   │   ├── sessions.py      # 会话管理（TTL、LRU、线程安全）
│   │   └── prompts.py       # 系统提示词 + 上下文构建
│   ├── api/
│   │   ├── deepseek.py      # OpenAI 兼容客户端（LLM + FC）
│   │   ├── llm_factory.py   # 多 Provider 工厂（DeepSeek/SiliconFlow/MiniMax）
│   │   ├── siliconflow.py   # SiliconFlow API（嵌入 + 重排 + LLM）
│   │   └── web_search.py    # 网络搜索（Tavily + DuckDuckGo）
│   ├── rag/
│   │   ├── retrievers.py    # 多通道检索（FAISS + BM25 + RRF）
│   │   ├── parent_document.py  # Parent Document 扩展（LRU 缓存）
│   │   ├── alias_map.py     # 干员别名映射
│   │   └── graphrag/        # 知识图谱
│   │       ├── builder.py   # 图谱构建（NetworkX DiGraph）
│   │       ├── extractor.py # 实体关系提取
│   │       └── query.py     # 图谱查询（单例）
│   ├── lc/
│   │   ├── embeddings.py    # LangChain Embeddings 封装
│   │   └── reranker.py      # LangChain Reranker 封装
│   ├── storage/
│   │   └── faiss_client.py  # FAISS 索引封装
│   ├── data/
│   │   ├── chunker.py       # 文本切块
│   │   └── bm25_index.py    # BM25 索引
│   ├── db.py                # SQLite 数据库（用户/会话）
│   └── auth.py              # JWT 认证
├── frontend/
│   └── src/
│       ├── views/
│       │   ├── ChatView.vue   # 问答界面（SSE 流式 + 工具卡片）
│       │   ├── AdminView.vue  # 管理面板（Chunk 可视化、仪表板）
│       │   └── GraphView.vue  # 知识图谱可视化（Cytoscape.js）
│       ├── stores/            # Pinia 状态管理
│       │   ├── sessions.js    # 会话管理
│       │   ├── auth.js        # 认证状态
│       │   ├── settings.js    # 模型/参数设置
│       │   └── quickQuestions.js  # 快捷问题
│       └── api.js             # API 客户端（Agent SSE）
├── data/                      # 原始数据（JSON/Markdown）
├── chunks/                    # 文本切块
├── faiss_index/               # FAISS 向量索引
├── Scripts/                   # 辅助脚本
└── tests/
```

## API 端点

### Agent

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/agent/chat` | Agent SSE 流式对话 |
| POST | `/agent/session` | 创建会话 |
| GET | `/agent/session/{id}/messages` | 获取消息历史 |
| DELETE | `/agent/session/{id}` | 删除会话 |
| GET | `/agent/models` | 可用模型列表 |
| GET | `/agent/debug/trace` | 工具调用追踪 |
| GET | `/agent/stats` | 会话统计 |

### 认证

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/auth/register` | 注册 |
| POST | `/auth/login` | 登录 |
| GET | `/auth/me` | 当前用户 |
| POST | `/auth/change-password` | 修改密码 |

### 会话管理

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/conversations` | 会话列表 |
| GET | `/conversations/{id}/messages` | 获取消息 |
| POST | `/conversations/sync` | 同步会话 |
| DELETE | `/conversations/{id}` | 删除会话 |
| PUT | `/conversations/{id}/rename` | 重命名 |

### 数据

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/status` | 配置状态 |
| GET | `/stats` | 系统统计 |
| GET | `/chunks/{collection}` | 切块列表 |
| GET | `/knowledge-graph` | 知识图谱数据 |
| GET | `/operators` | 干员列表 |
| GET | `/characters` | 角色列表 |
| GET | `/stories` | 故事列表 |
| GET | `/quick-questions` | 快捷问题 |

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| Agent LLM | DeepSeek-V3.2 / MiniMax-M2.5/M2.7（通过 llm_factory 统一调度） |
| 向量数据库 | FAISS |
| 嵌入模型 | BAAI/bge-m3（SiliconFlow） |
| 重排模型 | BAAI/bge-reranker-v2-m3（SiliconFlow） |
| 网络搜索 | Tavily + DuckDuckGo |
| 知识图谱 | NetworkX DiGraph |
| 数据库 | SQLite（aiosqlite） |
| 前端 | Vue.js 3 + Vite + Pinia |
| 图谱可视化 | Cytoscape.js |

## 缓存策略

| 缓存 | TTL | 说明 |
|------|-----|------|
| Agent 会话 | 3600s | 最大 1000 会话，LRU 驱逐 |
| Multi-Channel Recall | 5 小时 | 混合检索结果缓存 |
| Parent Document | 5 小时 | LRU 缓存，max 100 条 |
| BM25 索引 | 懒加载 | 首次召回时构建 |
| GraphBuilder | 懒加载 | 单例，线程安全 |

## Docker 部署

```bash
cp backend/.env.example backend/.env
# 编辑 .env 填入 API Keys
docker-compose up -d --build
```

MIT License
