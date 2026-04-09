# 明日方舟 RAG 助手

基于明日方舟数据集的智能问答助手，支持干员查询、剧情搜索、游戏攻略等检索场景。

## 功能特性

- **多路召回**：向量 + BM25 混合检索 + 标准 RRF 融合
- **Cross-Encoder Rerank**：BAAI/bge-reranker-v2-m3 精排
- **CRAG**：自适应检索策略（HIGH/LOW 二分类，网络搜索自动补足）
- **GraphRAG**：知识图谱关系查询（无需 LLM 判断）
- **查询改写**：fast_rule 快速匹配 + Qwen LLM 精判
- **Parent Document**：检索完整干员/剧情原文
- **Pipeline 详情**：显示 RAG 执行步骤及耗时
- **动态问题**：从真实数据生成随机问题按钮

## 系统要求

- **操作系统**：Windows 10/11、macOS 10.15+ 或 Linux
- **Python**：3.11+
- **内存**：至少 8 GB RAM（推荐 16 GB）

## 安装

### 1. 克隆代码

```bash
git clone <repo-url>
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
- **SiliconFlow API Key** - 向量嵌入 + 重排 + 查询改写（[siliconflow.cn](https://siliconflow.cn)）
- **DeepSeek API Key** - LLM 对话（[deepseek.com](https://deepseek.com)）

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
# 1. 生成文本切块（自动处理重复标题和微小 chunk 合并）
python backend/data/chunker.py

# 2. 生成 BM25 索引（保存为 chunks/*_bm25.pkl）
python backend/data/bm25_index.py

# 3. 生成向量数据库（需要 SiliconFlow API，强制重建所有索引）
python -c "
from backend.storage.index_manager import IndexManager
from backend.data.bm25_index import build_all_bm25_indexes

print('=== Building BM25 indexes ===')
build_all_bm25_indexes()

print('=== Building vector indexes ===')
manager = IndexManager()
manager.build_all_indexes(force=True)
"
```

## 启动服务

### 后端

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

## Docker 部署

### 环境要求

- Ubuntu 20.04+ (64位)
- Docker & Docker Compose
- 2GB+ 内存

### 快速部署

```bash
# 1. 克隆项目
git clone <repo-url>
cd RAG_ARKNIGHTS

# 2. 配置环境变量
cp backend/.env.example backend/.env
# 编辑 .env 填入 API Keys

# 3. 构建并启动
docker-compose up -d --build

# 4. 访问
# 前端界面: http://服务器IP:8000
# API 文档: http://服务器IP:8000/docs
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

## RAG 流程（8 步）

1. **查询改写** - fast_rule 快速匹配 + Qwen LLM 精判（判断是否检索、分解复杂问题）
2. **多路召回** - 并行 BM25 + 向量搜索，RRF 融合（operators/stories/knowledge 三个 collection）
3. **GraphRAG 查询**（与召回并行）- 知识图谱查询，用于实体关系问题
4. **Cross-Encoder 重排** - BAAI/bge-reranker-v2-m3
5. **CRAG 判断** - HIGH/LOW 二分类（低于阈值触发网络搜索）
6. **Parent Document** - 扩展为完整干员/剧情原文
7. **网络搜索** - CRAG LOW 时 Tavily 补充
8. **答案生成** - DeepSeek-V3 生成最终回答

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
│   ├── api/
│   │   ├── siliconflow.py   # SiliconFlow API（嵌入 + 重排 + 查询改写）
│   │   └── deepseek.py      # DeepSeek API（LLM 对话）
│   ├── rag/
│   │   ├── orchestrator.py    # RAG 流程编排（单例模式）
│   │   ├── query_rewriter.py  # 查询改写（fast_rule + Qwen）
│   │   ├── multi_channel_recall.py  # 多路召回（ThreadPoolExecutor 并发）
│   │   ├── hybrid_search.py   # 混合搜索（向量 + BM25 + 标准 RRF）
│   │   ├── reranker.py        # Cross-Encoder 重排
│   │   ├── crag.py            # CRAG 判断（HIGH/LOW 二分类）
│   │   ├── answer_generator.py # 答案生成（DeepSeek）
│   │   ├── parent_document.py  # Parent Document 扩展（LRU 缓存）
│   │   └── graphrag/          # 知识图谱
│   │       ├── builder.py     # 图谱构建（NetworkX）
│   │       └── query.py       # 图谱查询（无 LLM）
│   ├── storage/
│   │   ├── chroma_client.py   # ChromaDB 封装
│   │   └── index_manager.py   # 索引管理
│   └── data/
│       ├── bm25_index.py      # BM25 索引
│       └── chunker.py        # 文本切块
├── frontend/
│   └── src/
│       ├── views/
│       │   ├── ChatView.vue   # 问答界面
│       │   ├── AdminView.vue  # 管理面板（调试、评估）
│       │   └── GraphView.vue  # 知识图谱可视化
│       ├── stores/            # Pinia 状态
│       │   ├── sessions.js    # 会话管理
│       │   ├── settings.js    # 设置（CRAG/GraphRAG/ParentDoc）
│       │   └── quickQuestions.js  # 动态问题
│       └── api.js             # API 客户端
├── data/                     # 原始数据
├── chunks/                   # 文本切块
├── chroma_db/                # 向量数据库
└── eval/
    └── rag_eval.py           # RAG 评估
```

## API 端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/` | 服务状态 |
| GET | `/health` | 健康检查 |
| POST | `/query` | RAG 查询 |
| POST | `/debug/step` | 单步调试（1-8） |
| GET | `/chunks/{collection}` | 列出切块 |
| GET | `/chunks/{collection}/{filename}` | 获取切块内容 |
| GET | `/graph` | 知识图谱数据 |
| GET | `/stats` | 统计信息 |
| GET | `/operators` | 干员列表 |
| GET | `/characters` | 角色列表 |
| GET | `/stories` | 故事列表 |
| GET | `/eval` | 运行评估 |

## 前端功能

- **问答界面**：支持多会话、检索结果展示、pipeline 详情
- **管理面板**：单步调试、参数配置、评估对比
- **知识图谱**：实体关系可视化

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 向量数据库 | ChromaDB |
| 嵌入模型 | BAAI/bge-m3 (SiliconFlow) |
| 重排模型 | BAAI/bge-reranker-v2-m3 (SiliconFlow) |
| 查询改写 | Qwen/Qwen2.5-7B-Instruct (SiliconFlow) |
| 答案生成 | deepseek-chat (DeepSeek API) |
| 网络搜索 | Tavily |
| 前端 | Vue.js 3 + Vite + Pinia |
| 图谱可视化 | Cytoscape.js |

## 缓存策略

- **QueryRewriter**：5 小时 TTL，缓存 LLM 改写结果
- **Multi-Channel Recall**：5 小时 TTL
- **Hybrid Search**：5 小时 TTL，缓存 key 包含 vector_weight 和 inner_top_k
- **Parent Document**：LRU 缓存（max 100 条，5 小时 TTL）
- **BM25 索引**：懒加载，首次召回时构建

## 许可证

MIT License