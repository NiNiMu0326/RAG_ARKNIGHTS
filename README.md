# 明日方舟 ARKNIGHTS Agent

基于明日方舟数据集的 AI Agent 智能问答系统。Agent 通过 Function Calling 自主决定检索路径，支持知识库检索、知识图谱查询和网络搜索，可多工具并行调用、流式输出。

## 功能特性

- **AI Agent 自主决策**：LLM 通过 Function Calling 自主选择工具、并行执行、判断信息充足性，最多 8 轮工具调用
- **多 LLM 模型支持**：DeepSeek-V4-Flash、MiniMax-M2.5/M2.7，通过 llm\_factory 统一调度
- **知识库检索**：FAISS 向量 + BM25 关键词混合检索 → RRF 融合 → Cross-Encoder 重排 → Parent Document 扩展
- **知识图谱查询（GraphRAG）**：NetworkX 有向图，支持单实体邻居查询和双实体最短路径查找
- **网络搜索**：Tavily API + DuckDuckGo 兜底，补充外部实时信息
- **用户认证**：注册、登录、JWT 令牌认证，会话持久化到 SQLite
- **SSE 流式输出**：实时显示 Agent 思考过程、工具执行状态、流式回答生成
- **知识图谱可视化**：Cytoscape.js 交互式图谱，支持节点搜索、邻居展开、关系类型筛选

## 系统要求

- **Python**：3.11+
- **Node.js**：18+

## 快速开始

### 1. 克隆代码

```bash
git clone https://github.com/NiNiMu0326/RAG_ARKNIGHTS.git
cd RAG_ARKNIGHTS
```

### 2. 后端

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入 API Key
```

必需环境变量：

- `SILICONFLOW_API_KEY` - 向量嵌入 + 重排 + 默认 LLM（[siliconflow.cn](https://siliconflow.cn)）
- `JWT_SECRET` - JWT 签名密钥，生成方式：`python -c "import secrets; print(secrets.token_hex(32))"`

可选：

- `DEEPSEEK_API_KEY_2` - DeepSeek 官方模型
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
# 后端（默认端口 8889）
cd backend && uvicorn main:app --host 0.0.0.0 --port 8889

# 前端开发（端口 5300，通过 Vite 代理转发 API 请求）
cd frontend && npm run dev
```

访问 <http://localhost:5300>

## Agent 架构

```
用户消息 → 构建消息上下文 → LLM Function Calling → 选出工具 → 并行执行 → 结果注入消息
                                                      ↓ 无工具调用
                                                流式输出最终回答
```

Agent 自主循环：每轮 LLM 返回工具调用时并行执行，结果加入消息历史继续下一轮，直到模型认为信息充足或达到 8 轮上限。

**三个工具：**

| 工具                          | 功能     | 内部流程                                    |
| --------------------------- | ------ | --------------------------------------- |
| `arknights_rag_search`      | 知识库检索  | FAISS + BM25 → RRF 融合 → 重排 → Parent Doc |
| `arknights_graphrag_search` | 知识图谱查询 | 单实体邻居 / 双实体最短路径                         |
| `web_search`                | 网络搜索   | Tavily + DuckDuckGo                     |

**安全机制：** 最大 8 轮硬限制、循环检测（最近 3 轮相同 tool\_calls）、LLM 最大输出 token 限制

## 项目结构

```
.
├── backend/
│   ├── main.py                  # FastAPI 主应用，所有路由定义
│   ├── config.py                # 全局配置（API Keys、模型参数、路径）
│   ├── db.py                    # SQLite 数据库（aiosqlite）
│   ├── auth.py                  # JWT 用户认证
│   ├── requirements.txt
│   ├── agent/                   # Agent 核心
│   │   ├── core.py              # Agent 主循环（SSE、并行 FC、循环检测）
│   │   ├── tools.py             # 工具 Schema 定义 + ToolRegistry
│   │   ├── tool_implementations.py  # 三个工具实现 + BM25/GraphBuilder 懒加载单例
│   │   ├── sessions.py          # 会话管理（TTL 3600s、LRU、线程安全）
│   │   └── prompts.py           # 系统提示词 + 消息上下文构建
│   ├── api/                     # API 客户端封装
│   │   ├── deepseek.py          # OpenAI 兼容客户端（Chat + FC + 流式）
│   │   ├── llm_factory.py       # 多 Provider LLM 工厂
│   │   ├── siliconflow.py       # SiliconFlow API（嵌入 + 重排 + LLM）
│   │   └── web_search.py        # 网络搜索（Tavily + DuckDuckGo）
│   ├── rag/                     # RAG 底层基础设施
│   │   ├── retrievers.py        # 多通道检索（FAISS + BM25 + RRF），5h 缓存
│   │   ├── parent_document.py   # Parent Document 扩展（LRU 缓存）
│   │   ├── alias_map.py         # 干员别名映射
│   │   └── graphrag/            # 知识图谱
│   │       ├── builder.py       # 图谱构建（NetworkX DiGraph）
│   │       ├── extractor.py     # 实体关系提取
│   │       └── query.py         # 图谱查询（单例）
│   ├── lc/                      # LangChain 封装
│   │   ├── embeddings.py        # LangChain Embeddings 封装
│   │   └── reranker.py          # LangChain Reranker 封装
│   ├── storage/
│   │   └── faiss_client.py      # FAISS 向量索引封装
│   └── data/
│       ├── chunker.py           # 文本切块脚本
│       └── bm25_index.py        # BM25 索引构建脚本
├── frontend/
│   └── src/
│       ├── views/
│       │   ├── ChatView.vue     # 问答界面（SSE 流式 + 工具调用卡片 + 快捷问题）
│       │   ├── AdminView.vue    # 管理面板（Chunk 浏览器 + 数据仪表板）
│       │   └── GraphView.vue    # 知识图谱可视化（Cytoscape.js 交互）
│       ├── components/
│       │   ├── AppSidebar.vue   # 侧边栏（导航 + 会话管理 + 图谱控制）
│       │   ├── AppHeader.vue    # 顶部栏
│       │   ├── AuthModal.vue    # 登录/注册弹窗
│       │   ├── SettingsModal.vue # 设置弹窗（账户/主题/模型）
│       │   └── Toast.vue        # 通知提示
│       ├── stores/              # Pinia 状态管理
│       │   ├── sessions.js      # 会话管理
│       │   ├── auth.js          # 认证状态
│       │   ├── settings.js      # 主题/模型设置
│       │   ├── quickQuestions.js # 快捷问题缓存
│       │   └── toast.js         # 通知状态
│       ├── composables/
│       │   └── useGraphController.js  # 图谱控制器（单例，跨组件共享）
│       └── api.js               # API 客户端（含 Agent SSE 流式调用）
├── data/                        # 原始数据集（JSON/Markdown）
├── chunks/                      # 文本切块输出
├── faiss_index/                 # FAISS 向量索引持久化
├── Scripts/                     # 辅助脚本
└── tests/
```

## API 端点

### Agent

| 方法     | 路径                             | 描述             |
| ------ | ------------------------------ | -------------- |
| POST   | `/agent/chat`                  | Agent SSE 流式对话 |
| POST   | `/agent/session`               | 创建会话           |
| GET    | `/agent/session/{id}/messages` | 获取消息历史         |
| DELETE | `/agent/session/{id}`          | 删除会话           |
| GET    | `/agent/models`                | 可用模型列表         |
| GET    | `/agent/stats`                 | 会话统计           |

### 认证

| 方法   | 路径                      | 描述   |
| ---- | ----------------------- | ---- |
| POST | `/auth/register`        | 注册   |
| POST | `/auth/login`           | 登录   |
| GET  | `/auth/me`              | 当前用户 |
| POST | `/auth/change-password` | 修改密码 |

### 会话管理

| 方法     | 路径                             | 描述   |
| ------ | ------------------------------ | ---- |
| GET    | `/conversations`               | 会话列表 |
| GET    | `/conversations/{id}/messages` | 获取消息 |
| POST   | `/conversations/sync`          | 同步会话 |
| DELETE | `/conversations/{id}`          | 删除会话 |
| PUT    | `/conversations/{id}/rename`   | 重命名  |

### 数据

| 方法  | 路径                     | 描述     |
| --- | ---------------------- | ------ |
| GET | `/health`              | 健康检查   |
| GET | `/status`              | 配置状态   |
| GET | `/stats`               | 系统统计   |
| GET | `/chunks/{collection}` | 切块列表   |
| GET | `/knowledge-graph`     | 知识图谱数据 |
| GET | `/operators`           | 干员列表   |
| GET | `/characters`          | 角色列表   |
| GET | `/stories`             | 故事列表   |
| GET | `/quick-questions`     | 快捷问题   |

## 技术栈

| 组件        | 技术                                                      |
| --------- | ------------------------------------------------------- |
| 后端框架      | FastAPI + Uvicorn                                       |
| Agent LLM | DeepSeek-V3.2 / MiniMax-M2.5/M2.7（通过 llm\_factory 统一调度） |
| 向量数据库     | FAISS                                                   |
| 嵌入模型      | BAAI/bge-m3（SiliconFlow）                                |
| 重排模型      | BAAI/bge-reranker-v2-m3（SiliconFlow）                    |
| 网络搜索      | Tavily + DuckDuckGo                                     |
| 知识图谱      | NetworkX DiGraph                                        |
| 数据库       | SQLite（aiosqlite）                                       |
| 前端        | Vue.js 3 + Vite + Pinia                                 |
| 图谱可视化     | Cytoscape.js                                            |

## 缓存策略

| 缓存              | TTL   | 说明                      |
| --------------- | ----- | ----------------------- |
| Agent 会话        | 3600s | 最大 1000 会话，LRU 驱逐       |
| 混合检索结果          | 5 小时  | FAISS + BM25 RRF 融合结果缓存 |
| Parent Document | 5 小时  | LRU 缓存，最大 100 条         |
| BM25 索引         | 懒加载   | 首次召回时构建，线程安全            |
| 知识图谱            | 懒加载   | 单例，线程安全                 |

## SSE 事件类型

Agent 流式对话使用以下 SSE 事件：

| 事件                 | 描述          |
| ------------------ | ----------- |
| `thinking_start`   | Agent 开始思考  |
| `thinking_delta`   | 思考增量内容      |
| `tool_calls_start` | 开始执行工具调用    |
| `tool_executing`   | 单个工具执行中     |
| `tool_call_result` | 工具执行完成（含结果） |
| `answer_delta`     | 回答增量内容（流式）  |
| `answer_done`      | 回答完成        |
| `error`            | 错误信息        |

MIT License
