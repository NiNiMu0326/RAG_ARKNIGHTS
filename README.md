# 明日方舟 RAG 助手

基于明日方舟数据集的智能问答助手，支持干员查询、剧情搜索、游戏攻略、梗百科等多种检索场景。

## 功能特性

- 🔍 **多路召回**：向量 + BM25 混合检索
- 🎯 **Cross-Encoder Rerank**：精排 Top-5
- 🔄 **CRAG**：自适应检索策略（网络搜索自动补足低相关场景）
- 🕸️ **GraphRAG**：知识图谱关系查询 + 可视化
- 💬 **查询分解**：多实体问题分解并行召回
- 📄 **Parent Document**：检索完整干员/剧情原文
- 📊 **管理面板**：索引管理 / RAG 调试 / 参数对比 / LLM 评估
- 🌐 **流式输出**：SSE 实时响应，显示 RAG 执行步骤
- 🎨 **战术指挥中心界面**：明日方舟主题深色科技感设计

## 系统要求

- **操作系统**：Windows 10/11、macOS 10.15+ 或 Linux（Ubuntu 20.04+ 推荐）
- **Python**：3.11 或更高版本（推荐使用 Anaconda/Miniconda）
- **内存**：至少 8 GB RAM（推荐 16 GB）
- **磁盘空间**：至少 2 GB 可用空间

## 📦 安装指南

### 1. 获取代码

```bash
# 克隆仓库
git clone https://github.com/your-username/RAG_ARKNIGHTS.git
cd RAG_ARKNIGHTS
```

### 2. 安装 Miniconda（如未安装）

#### Windows
1. 下载 Miniconda 安装程序：https://docs.conda.io/en/latest/miniconda.html
2. 运行安装程序，按默认设置安装
3. 打开 "Anaconda Prompt"（开始菜单中搜索）

#### macOS/Linux
```bash
# 下载安装脚本
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
# 或
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh

# 运行安装
bash Miniconda3-latest-Linux-x86_64.sh
# 按照提示操作，安装完成后重启终端
```

### 3. 创建 Python 环境

```bash
# 创建名为 arknights-rag 的 Python 3.11 环境
conda create -n arknights-rag python=3.11 -y

# 激活环境
conda activate arknights-rag
```

### 4. 安装后端依赖

```bash
# 进入后端目录
cd backend

# 安装 Python 依赖包
pip install -r requirements.txt
```

> **注意**：安装可能需要几分钟，具体时间取决于网络速度和系统性能。

## ⚙️ 配置

### 1. 配置 API Keys

项目需要以下 API Key（至少需要 SiliconFlow API Key）：

1. **SiliconFlow API Key**（必需）
   - 访问 https://siliconflow.cn 注册账号
   - 在控制台创建 API Key
   - 免费额度足够测试使用

2. **Tavily API Key**（可选，用于网络搜索功能）
   - 访问 https://tavily.com 注册账号
   - 获取 API Key
   - 如果不配置，网络搜索功能将不可用

### 2. 设置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入你的 API Key
# 可以使用文本编辑器（如 nano、vim、记事本等）
```

`.env` 文件内容示例：
```env
# SiliconFlow API Key (required)
SILICONFLOW_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Tavily API Key for internet search (optional)
TAVILY_API_KEY=tvly-dev-xxxxxxxxxxxxxxxxxxxxxxxx

# Server Port (optional, defaults to 8000)
PORT=8000
```

## 📊 数据处理

本项目提供完整的原始数据文件（`data/`目录），但处理后的中间文件（`chunks/`和`chroma_db/`）需要用户自行生成。这样做可以显著减小仓库体积，并让用户了解完整的数据处理流程。

### 1. 生成文本切块（chunks/）

```bash
# 确保在项目根目录，并已激活 conda 环境
conda activate arknights-rag

# 运行文本切块程序
python backend/data/chunker.py
```
这将读取 `data/` 目录下的原始文件，生成 `chunks/` 目录。处理时间约为 1-2 分钟。

### 2. 生成 BM25 索引

```bash
# 运行 BM25 索引构建
python backend/data/bm25_index.py
```
这会为 `chunks/` 中的三个集合（operators, stories, knowledge）分别构建 BM25 索引，保存为 `.pkl` 文件。

### 3. 生成向量数据库索引（chroma_db/）

> **注意**：此步骤需要有效的 SiliconFlow API Key，并会产生 API 调用费用（免费额度充足）。

```bash
# 运行 ChromaDB 索引构建
python backend/storage/index_manager.py
```
程序会提示确认，输入 `y` 继续。此步骤会：
- 读取 `chunks/` 目录中的所有文本
- 通过 SiliconFlow API 生成文本嵌入向量
- 构建向量数据库索引到 `chroma_db/` 目录
- 处理约 13,000 个文本块，需要几分钟时间

### 数据处理注意事项
1. **首次运行**：建议按顺序执行上述三个步骤
2. **重新生成**：如果修改了原始数据，需要重新执行所有步骤
3. **磁盘空间**：完整处理需要约 300MB 额外空间
4. **API 费用**：步骤3会消耗 SiliconFlow API 调用次数，但免费额度足够多次使用

## 🚀 启动服务

### 1. 启动后端服务

```bash
# 确保在 backend 目录中
cd backend

# 激活 conda 环境（如果尚未激活）
conda activate arknights-rag

# 启动 FastAPI 服务
uvicorn main:app --host 0.0.0.0 --port 8000
```

正常启动后，终端将显示：
```
INFO:     Started server process [PID]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 2. 启动前端服务（两种方式）

#### 方式一：使用预构建的静态文件（最简单，无需 Node.js）
项目已包含预构建的前端文件，可以直接使用：
```bash
# 打开新的终端窗口，切换到项目根目录
cd RAG_ARKNIGHTS

# 启动 HTTP 服务器（端口 8080），服务构建好的前端文件
python -m http.server 8080 --directory frontend/dist
```

> **注意**：预构建文件使用默认的 `http://localhost:8000` 作为后端地址。如需更改，请使用方式二。

#### 方式二：使用 Node.js 开发服务器（推荐用于开发）
```bash
# 进入前端目录
cd frontend

# 安装依赖（首次运行）
npm install

# 启动开发服务器
npm run dev
```
开发服务器将在 `http://localhost:5173` 启动，并支持热重载。

### 3. 配置前端 API 地址

前端默认连接 `http://localhost:8000` 的后端。如需更改，有以下几种方式：

#### 方法A：使用环境变量（推荐）
1. **创建环境文件**：
   ```bash
   cd frontend
   cp .env.example .env
   ```

2. **编辑 `.env` 文件**，修改 `VITE_API_BASE`：
   ```env
   # 例如，如果后端运行在 192.168.1.100:8000
   VITE_API_BASE=http://192.168.1.100:8000
   ```

3. **应用配置**：
   - **开发模式** (`npm run dev`)：环境变量自动生效
   - **生产构建**：重新构建以应用新配置：
     ```bash
     cd frontend
     npm run build  # 构建到 dist/ 目录
     ```

#### 方法B：直接修改源码（不推荐，仅用于快速测试）
修改 `frontend/src/api.js` 和 `frontend/src/api/index.js` 中的 `API_BASE` 变量。

#### 配置示例

**场景1：本地开发，后端在默认端口**
- 无需任何配置，直接使用默认值

**场景2：后端在另一台服务器**
```bash
# 1. 创建环境文件
cd frontend
cp .env.example .env

# 2. 编辑 .env，例如：
# VITE_API_BASE=http://192.168.1.100:8000

# 3A. 开发模式：直接运行
npm run dev

# 3B. 生产模式：构建后使用
npm run build
python -m http.server 8080 --directory dist
```

**场景3：使用 Docker 或容器化部署**
```env
# .env 文件内容
VITE_API_BASE=http://backend:8000  # Docker 容器名

## 🌐 访问应用

启动成功后，可以通过以下地址访问：

- **前端界面**：http://localhost:8080
- **后端 API**：http://localhost:8000
- **API 文档**：http://localhost:8000/docs（自动生成的 Swagger UI）

### 验证服务状态

打开浏览器访问 http://localhost:8000，应该看到：
```json
{"message": "Arknights RAG API", "version": "1.0.0"}
```

## 📁 项目结构

```
RAG_ARKNIGHTS/
├── backend/                    # FastAPI 后端服务
│   ├── main.py                # FastAPI 主应用
│   ├── config.py              # 配置文件（路径设置）
│   ├── requirements.txt       # Python 依赖列表
│   ├── .env.example           # 环境变量示例
│   ├── rag/                   # RAG 核心模块
│   │   ├── orchestrator.py    # RAG 流程编排器
│   │   ├── multi_channel_recall.py  # 多路召回
│   │   ├── reranker.py        # 交叉编码器重排
│   │   ├── crag.py            # CRAG 判断模块
│   │   ├── answer_generator.py # 答案生成器
│   │   ├── graphrag/          # GraphRAG 知识图谱
│   │   └── parent_document.py # Parent Document 检索
│   ├── api/                   # 外部 API 客户端
│   │   └── siliconflow.py     # SiliconFlow API 封装
│   ├── storage/               # 数据存储
│   │   ├── chroma_client.py   # ChromaDB 客户端
│   │   └── index_manager.py   # 索引管理
│   ├── data/                  # 数据处理模块
│   │   ├── bm25_index.py      # BM25 索引
│   │   ├── chunker.py         # 文本切块
│   │   ├── loader.py          # 数据加载
│   │   └── operators_summary.py # 干员摘要处理
│   └── tests/                 # 单元测试
├── frontend/                  # Vue.js 前端界面
│   ├── index.html             # 主页面
│   ├── package.json           # Node.js 依赖
│   ├── vite.config.js         # Vite 配置
│   ├── src/                   # 源代码
│   │   ├── main.js            # Vue 应用入口
│   │   ├── App.vue            # 根组件
│   │   ├── views/             # 页面组件
│   │   ├── components/        # 通用组件
│   │   ├── stores/            # Pinia 状态管理
│   │   ├── router/            # 路由配置
│   │   ├── api/               # API 客户端
│   │   └── utils/             # 工具函数
│   └── dist/                  # 构建输出（预构建）
├── data/                      # 原始数据文件（已包含）
│   ├── operators/             # 干员数据
│   ├── stories/               # 剧情数据
│   ├── knowledge/             # 游戏知识
│   ├── all_operators.json     # 所有干员列表
│   └── char_summary.md        # 角色摘要
├── chunks/                    # 文本切块数据（需通过数据处理生成）
│   ├── operators/             # 干员切块
│   ├── stories/               # 剧情切块
│   └── knowledge/             # 知识切块
├── chroma_db/                 # ChromaDB 向量数据库（需通过数据处理生成）
├── eval/                      # 评估模块
│   ├── rag_eval.py            # RAG 评估器
│   └── questions.json         # 评估问题集
├── .gitignore                 # Git 忽略文件
└── README.md                  # 项目说明
```

## 🔧 API 接口

### 核心问答接口
- `POST /query` - 执行 RAG 查询，返回答案和元数据
- `POST /query/stream` - 流式查询（SSE 事件流）
- `POST /debug/step` - 分步调试 RAG 流程

### 数据管理接口
- `GET /chunks/{collection}` - 列出指定集合的 chunk 文件
- `GET /chunks/{collection}/{filename}` - 获取 chunk 内容
- `GET /graph` - 获取知识图谱数据
- `GET /stats` - 获取系统统计信息
- `GET /operators` - 获取所有干员名列表
- `GET /characters` - 获取所有角色名列表
- `GET /stories` - 获取所有故事名列表

### 评估接口
- `GET /eval` - 运行 RAG 评估

## 🔍 使用示例

### 1. 基本问答
在聊天界面输入问题，例如：
- "银灰的技能是什么？"
- "阿米娅和博士是什么关系？"
- "明日方舟有哪些六星干员？"

### 2. 调试模式
点击"调试模式"按钮，可以：
- 查看 RAG 流程的每个步骤
- 检查召回文档的内容
- 分析 CRAG 判断结果
- 观察知识图谱查询结果

### 3. 管理后台
访问管理面板可以：
- 查看系统统计信息
- 浏览向量数据库内容
- 运行 RAG 评估测试
- 调整检索参数

## 🐛 故障排除

### 常见问题

#### 1. 后端启动失败
- **错误**：`ModuleNotFoundError: No module named 'fastapi'`
- **解决**：确保已激活 conda 环境并安装依赖：`pip install -r requirements.txt`

#### 2. 前端无法连接后端
- **现象**：前端显示"连接失败"或一直加载
- **解决**：
  1. 检查后端是否正常运行：访问 http://localhost:8000
  2. 检查前端 `API_BASE` 设置是否匹配后端地址
  3. 检查防火墙设置，确保端口 8000 和 8080 开放

#### 3. API Key 错误
- **错误**：`Invalid API Key` 或 `Authentication failed`
- **解决**：
  1. 检查 `.env` 文件中的 `SILICONFLOW_API_KEY` 是否正确
  2. 确认 API Key 是否有效（在 SiliconFlow 控制台验证）
  3. 确保 `.env` 文件在 `backend` 目录中

#### 4. 内存不足
- **现象**：程序运行缓慢或崩溃
- **解决**：
  1. 关闭不必要的应用程序
  2. 减少检索参数（如 `top_k` 值）
  3. 考虑升级系统内存

### 日志查看

#### 后端日志
```bash
# 查看后端输出（如果直接运行）
# 日志显示在启动后端服务的终端中

# 如果使用 nohup 后台运行
tail -f backend.log
```

#### 前端日志
- 浏览器开发者工具（F12）→ Console 标签页
- 查看网络请求和错误信息

## 📚 技术栈

### 后端技术
- **框架**：FastAPI + Uvicorn
- **向量数据库**：ChromaDB
- **检索算法**：BM25 + 向量相似度
- **重排序**：BAAI/bge-reranker-v2-m3
- **嵌入模型**：BAAI/bge-m3
- **LLM**：DeepSeek-V3（通过 SiliconFlow）
- **数据处理**：Pandas, NumPy, scikit-learn

### 前端技术
- **框架**：Vue.js 3 + Composition API
- **状态管理**：Pinia
- **路由**：Vue Router
- **构建工具**：Vite
- **可视化**：Cytoscape.js（知识图谱）
- **样式**：CSS3 + 自定义明日方舟主题

### 开发工具
- **版本控制**：Git
- **环境管理**：Miniconda
- **包管理**：pip + npm
- **API 文档**：Swagger UI（自动生成）

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/amazing-feature`
3. 提交更改：`git commit -m 'Add amazing feature'`
4. 推送到分支：`git push origin feature/amazing-feature`
5. 开启 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- 感谢明日方舟游戏开发团队提供丰富的游戏内容
- 感谢 SiliconFlow 提供优质的 LLM API 服务
- 感谢所有开源项目的贡献者

---

**提示**：本项目仅供学习和研究使用。游戏内容版权属于上海鹰角网络科技有限公司。