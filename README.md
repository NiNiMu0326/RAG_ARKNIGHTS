# 明日方舟 RAG 助手

基于明日方舟数据集的智能问答助手，支持干员查询、剧情搜索、游戏攻略等检索场景。

## 功能特性

- **AgenticRAG**：DeepSeek-chat Function Calling 自主决定检索路径
- **并行工具调用**：Agent 可同时发起多个工具调用，提升效率
- **SSE 流式输出**：实时显示 Agent 思考过程和工具执行状态
- **知识库检索**：FAISS 向量 + BM25 混合检索 + Cross-Encoder 重排
- **GraphRAG**：知识图谱实体关系查询（单实体邻居 / 双实体路径）
- **网络搜索**：Tavily + DuckDuckGo 补充外部信息
- **会话管理**：后端会话存储，支持多轮对话上下文
- **PipelineRAG 兼容**：旧版8步固定流程仍可使用

## 系统要求

- **操作系统**：Windows 10/11、macOS 10.15+ 或 Linux
- **Python**：3.11+
- **内存**：至少 8 GB RAM（推荐 16 GB）

## 安装

### 1. 克隆代码

```bash
git clone https://github.com/NiNiMu0326/RAG_ARKNIGHTS.git
cd RAG_ARKNIGHTS
```

### 2. 创建 Python 环境

```bash
conda create -n arknights-rag python=3.11 -y
conda activate arknights-rag
```

### 3. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 4. 配置 API Keys

```bash
cp .env.example .env
# 编辑 .env 填入 API Key
```

必需：
- **SiliconFlow API Key** - 向量嵌入 + 重排 + 查询改写 + 答案生成（[siliconflow.cn](https://siliconflow.cn)）

可选：
- **Tavily API Key** - 网络搜索补充（[tavily.com](https://tavily.com)）

## 数据处理

### 文本切块策略

- **实时分割合并算法**：处理每个段落时立即检查合并条件，避免过度分割
- **干员/敌人数据**：每个干员/敌人一个完整 chunk（无大小限制）
- **剧情/知识数据**：min_size=1500字符，target_size=4000字符，max_size=6000字符
- **标题处理**：每个 chunk 开头添加干员/剧情标题
- **Markdown 分段**：按 `##` 标题分割，超大章节递归拆分

### 构建索引

```bash
# 1. 生成文本切块
python backend/data/chunker.py

# 2. 生成 BM25 索引（保存为 chunks/*_bm25.pkl）
python backend/data/bm25_index.py

# 3. 生成 FAISS 向量索引（需要 SiliconFlow API）
python backend/build_faiss_index.py
```

## 启动服务

### 后端

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8889
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5175

## Docker 部署

### 环境要求

- Ubuntu 20.04+ (64位)
- Docker & Docker Compose
- 2GB+ 内存

### 快速部署

```bash
# 1. 克隆项目
git clone https://github.com/NiNiMu0326/RAG_ARKNIGHTS.git
cd RAG_ARKNIGHTS

# 2. 配置环境变量
cp backend/.env.example backend/.env
# 编辑 .env 填入 API Keys

# 3. 构建并启动
docker-compose up -d --build

# 4. 访问
# 前端界面: http://服务器IP:5175
# API 文档: http://服务器IP:8889/docs
```

### 常用命令

```bash
# 查看容器状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 重启服务
docker-compose restart

# 停止服务
docker-compose down
```

## RAG 流程

### AgenticRAG（主要模式）

DeepSeek-chat Agent 自主决定检索路径，通过 Function Calling 调用工具：

1. **用户提问** → Agent 判断需要哪些工具
2. **并行工具调用** - 同时发起多个无依赖的工具调用
3. **串行依赖调用** - 后续查询依赖前次结果时分步调用
4. **信息充足性判断** - 足够则生成回答，不足则补充检索
5. **生成回答** - 基于检索结果生成最终回答

**三个工具：**
- `arknights_rag_search` - 知识库检索（向量 + BM25 + 重排 + Parent Doc）
- `arknights_graphrag_search` - 知识图谱查询（实体邻居 / 关系路径）
- `web_search` - 网络搜索（Tavily + DuckDuckGo）

**安全机制：** 最大8轮调用、循环检测、SSE 流式输出

### PipelineRAG（兼容模式，`/query` 端点）

1. **查询改写** - fast_rule + Qwen LLM
2. **多路召回** - BM25 + FAISS 向量，RRF 融合
3. **GraphRAG 查询** - 知识图谱
4. **Cross-Encoder 重排** - BAAI/bge-reranker-v2-m3
5. **CRAG 判断** - HIGH/LOW 二分类
6. **Parent Document** - 扩展完整原文
7. **网络搜索** - CRAG LOW 时补充
8. **答案生成** - DeepSeek 生成回答

## 参数配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `top_k_per_channel` | 8 | 每库召回数量 |
| `rerank_top_k` | 5 | 重排输出数量 |
| `vector_weight` | 0.5 | 向量/BM25 权重 |
| `inner_top_k` | 20 | 内部搜索数量 |

## 项目结构

```
RAG_ARKNIGHTS/
├── backend/
│   ├── main.py              # FastAPI 主应用
│   ├── config.py            # 配置（API Keys、模型参数）
│   ├── requirements.txt     # Python 依赖
│   ├── agent/               # AgenticRAG 核心
│   │   ├── core.py          # Agent 主循环（SSE、并行 FC、循环检测）
│   │   ├── tools.py         # 工具 Schema + ToolRegistry
│   │   ├── tool_implementations.py  # 工具实现（RAG/GraphRAG/Web）
│   │   ├── sessions.py      # 会话管理（TTL、LRU）
│   │   └── prompts.py       # 系统提示词
│   ├── api/
│   │   ├── siliconflow.py  # SiliconFlow API（嵌入 + 重排 + 网络搜索）
│   │   └── deepseek.py     # DeepSeek API（LLM + Function Calling）
│   ├── rag/
│   │   ├── orchestrator.py  # PipelineRAG 编排器
│   │   ├── chain.py        # LangChain LCEL 流程
│   │   ├── query_rewriter.py  # 查询改写（fast_rule + Qwen）
│   │   ├── retrievers.py    # 多路召回（FAISS + BM25 + RRF）
│   │   ├── crag.py        # CRAG 判断（HIGH/LOW 二分类）
│   │   ├── answer_generator.py  # 答案生成
│   │   ├── parent_document.py  # Parent Document 扩展
│   │   └── graphrag/      # 知识图谱
│   │       ├── builder.py # 图谱构建（NetworkX DiGraph）
│   │       ├── extractor.py # 实体关系提取
│   │       └── query.py  # 图谱查询
│   ├── storage/
│   │   └── faiss_client.py  # FAISS 索引封装
│   ├── data/
│   │   ├── bm25_index.py  # BM25 索引
│   │   └── chunker.py    # 文本切块
│   └── lc/
│       ├── embeddings.py   # LangChain 嵌入
│       ├── reranker.py   # LangChain 重排
│       └── llm.py       # LangChain LLM
├── frontend/
│   └── src/
│       ├── views/
│       │   ├── ChatView.vue   # 问答界面（SSE 流式 + 工具卡片）
│       │   ├── AdminView.vue  # 管理面板（调试、评估）
│       │   └── GraphView.vue  # 知识图谱可视化
│       ├── stores/       # Pinia 状态
│       │   ├── sessions.js
│       │   ├── settings.js
│       │   └── quickQuestions.js
│       └── api.js       # API 客户端（含 Agent SSE）
├── data/                   # 原始数据
├── chunks/                 # 文本切块
├── faiss_index/            # FAISS 向量索引
├── Scripts/
│   └── scraper.py          # PRTS Wiki 数据爬虫
└── eval/
    ├── rag_eval.py         # RAG 评估模块
    ├── run_eval.py         # 评估运行脚本
    └── questions.json      # 评估问题集
```

## API 端点

### AgenticRAG（主要）

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/agent/session` | 创建 Agent 会话 |
| POST | `/agent/chat` | Agent SSE 流式对话 |
| GET | `/agent/session/{id}/messages` | 获取消息历史 |
| DELETE | `/agent/session/{id}` | 删除会话 |
| GET | `/agent/debug/trace` | 调试追踪 |
| GET | `/agent/stats` | 会话统计 |

### PipelineRAG（兼容）

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/query` | PipelineRAG 查询 |
| POST | `/debug/step` | 单步调试（1-8） |

### 其他

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api` | 服务状态 |
| GET | `/health` | 健康检查 |
| GET | `/status` | 配置状态 |
| GET | `/chunks/{collection}` | 列出切块 |
| GET | `/chunks/{collection}/{filename}` | 获取切块内容 |
| GET | `/knowledge-graph` | 知识图谱数据 |
| GET | `/stats` | 统计信息 |
| GET | `/operators` | 干员列表 |
| GET | `/characters` | 角色列表 |
| GET | `/stories` | 故事列表 |
| GET | `/eval/stream` | SSE 评估 |
| POST | `/eval/start` | 后台评估 |

## 前端功能

- **问答界面**：SSE 流式输出、工具调用卡片、多会话支持
- **管理面板**：单步调试、参数配置、评估对比
- **知识图谱**：实体关系可视化

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| Agent LLM | DeepSeek-chat (Function Calling) |
| 向量数据库 | FAISS |
| 嵌入模型 | BAAI/bge-m3 (SiliconFlow Pro) |
| 重排模型 | BAAI/bge-reranker-v2-m3 (SiliconFlow) |
| 查询改写 | Qwen/Qwen2.5-7B-Instruct (SiliconFlow Pro) |
| 答案生成 | DeepSeek-chat |
| 网络搜索 | Tavily + DuckDuckGo (SiliconFlow) |
| 知识图谱 | NetworkX DiGraph |
| 前端 | Vue.js 3 + Vite + Pinia |
| 图谱可视化 | Cytoscape.js |

## 缓存策略


- **Agent 会话**：TTL 3600s，最大 1000 会话，LRU 驱逐
- **QueryRewriter**：5 小时 TTL，缓存 LLM 改写结果
- **Multi-Channel Recall**：5 小时 TTL
- **Parent Document**：LRU 缓存（max 100 条，5 小时 TTL）
- **BM25 索引**：懒加载，首次召回时构建
- **GraphBuilder**：懒加载单例



MIT License