# 代码审查问题清单

> 审查日期：2026-04-26 | 审查范围：前后端全量代码

---

## 严重（建议立即修复）

### 1. 双数据库系统 — 死代码

`backend/database/` 目录（~278行）是一套基于同步 sqlite3 的数据库实现，`main.py` 实际使用的是 `backend/db.py`（aiosqlite 异步版），两套 schema 不一致（一个有 `account` 字段、一个没有）。

**文件：**
- `backend/database/db.py` — `Database` 类，从未被引用
- `backend/database/__init__.py` — 仅导出 `Database`

**建议：** 删除整个 `backend/database/` 目录。

---

### 2. JWT 密钥硬编码默认值

**文件：** `backend/auth.py:11`

```python
JWT_SECRET = os.environ.get("JWT_SECRET", "arknights-rag-jwt-secret-change-in-production")
```

如果生产环境忘记设置 `JWT_SECRET` 环境变量，任何人可伪造 token。

**建议：** 生产环境不做 fallback，检测到默认值时报错退出。

---

### 3. 前端大量死代码（~700行）

| 文件 | 行数 | 说明 |
|------|------|------|
| `frontend/src/stores/graph.js` | ~165行 | 完全未被引用，图谱状态走 `useGraphController` |
| `frontend/src/utils/quickQuestions.js` | ~240行 | 从未被导入，`ChatView` 直接调 API |
| `frontend/src/utils/dataLoader.js` | 全部 | 所有函数返回 `[]`，从未被导入 |
| `frontend/src/api/index.js` | 1行 | 空文件 |
| `frontend/src/api.js` 中的 `debounce`、`truncate` | — | 导出但从未被使用 |

**建议：** 删除以上所有文件及函数。

---

### 4. AppSidebar 事件监听器未清理 — 内存泄漏风险

**文件：** `frontend/src/components/AppSidebar.vue`

`onMounted` 中注册了 `window.addEventListener('auth-changed', ...)` 但 `onUnmounted` 中没有 `removeEventListener`。

当前因 `<keep-alive>` 组件不销毁所以暂未暴露，但未来改动可能触发内存泄漏。

**建议：** 在 `onUnmounted` 中移除监听器。

---

## 中等（尽快修复）

### 5. 重复的 `<think>` 标签解析逻辑

**文件：**
- `backend/api/deepseek.py:270-397` — API 客户端层解析
- `backend/agent/core.py:392-515` — Agent 循环层再次解析

两处实现不一致（deepseek.py 用 `re.match`，core.py 用手动字符串查找），且有冗余处理。

**建议：** 只在 deepseek.py 客户端层解析，core.py 移除重复逻辑；或反过来，统一在一处处理。

---

### 6. 前端 SSE 事件分发重复代码

**文件：** `frontend/src/api.js`

`agentChat` 方法中 switch 语句在流循环内（lines 259-284）和流结束后的尾部 buffer 处理（lines 297-306）完全重复。

**建议：** 抽取为共享的 `_dispatchSSEEvent(event, callbacks)` 函数。

---

### 7. ChatView 重复 CSS

**文件：** `frontend/src/views/ChatView.vue`

`.quick-action` 相关 CSS 规则出现了两次（line 770-773 和 line 834-837）。

**建议：** 删除重复的一份。

---

### 8. useGraphController 中 `selectedEdge` 被遮蔽

**文件：**
- `frontend/src/composables/useGraphController.js` — 导出 `selectedEdge` ref
- `frontend/src/views/GraphView.vue` — 自己声明了同名 `selectedEdge` ref

两个是不同的变量，`controller.clearSelection()` 操作 controller 的，GraphView 读取自己的——清空选中实际无效。

**建议：** GraphView 移除自己的 `selectedEdge`，统一使用 controller 导出的。

---

### 9. 后端未使用的模块和函数

| 文件 | 未使用部分 | 说明 |
|------|-----------|------|
| `backend/rag/graphrag/query.py` | `GraphRAGQuery` 类 | 全类未被引用 |
| `backend/api/siliconflow.py` | `chat()` 方法 | LLM 统一走 `DeepSeekClient` |
| `backend/rag/graphrag/query.py` + `backend/agent/tool_implementations.py` | `get_graph_builder()` | 两个文件各自实现了相同的懒加载单例 |

**建议：** 删除未使用代码，合并重复的 `get_graph_builder` 到一处。

---

### 10. build_graphrag.py 路径不一致

**文件：** `backend/build_graphrag.py`

- `build_operators()` 使用 `config.ENTITY_RELATIONS_FILE`
- `build_stories()` 和 `build_all()` 使用 `SCRIPT_DIR / 'chunks' / 'graphrag' / 'entity_relations.json'`

可能写入不同位置。

**建议：** 统一使用 `config.ENTITY_RELATIONS_FILE`。

---

### 11. 前端无路由守卫

**文件：** `frontend/src/router/index.js`

无 `beforeEach` 守卫，Admin 页面无认证保护（服务端有校验但无前端提示）。

**建议：** 添加路由守卫，未登录用户访问受保护页面时重定向或弹登录框。

---

## 轻微（择机修复）

### 后端

| # | 文件 | 问题 |
|---|------|------|
| 12 | `backend/agent/tool_implementations.py:101` | `execute_graphrag_search` 导入 `GraphBuilder` 但未直接使用 |
| 13 | `backend/agent/tool_implementations.py:32-34` | `execute_rag_search` 导入 `BM25Indexer`、`Path` 但未直接使用 |
| 14 | `backend/main.py:39-44` | 对 `config` 双重导入（`from config import (...)` + `import config as config`） |
| 15 | `backend/main.py:525` | `X-New-Session-Id` 无新会话也设空字符串 header |
| 16 | `backend/main.py:470` | `rename_conversation` 接受空 `name` 参数，无校验 |
| 17 | `backend/agent/sessions.py` | `SessionManager` 使用 `threading.Lock()` 但上下文是 asyncio |
| 18 | `backend/agent/core.py:195-211` | `INJECTION_PATTERNS` 中 `你是...` 等正则有中文误判风险 |
| 19 | `backend/main.py` 启动逻辑 | 未验证 `SILICONFLOW_API_KEY` 是否配置，运行时才报错 |

### 前端

| # | 文件 | 问题 |
|---|------|------|
| 20 | `frontend/src/views/ChatView.vue:247` | 导入 `computed` 但未使用 |
| 21 | `frontend/src/views/ChatView.vue:18` | 消息列表 `v-for` 使用 `:key="idx"`（数组下标），不符合 Vue 最佳实践 |
| 22 | `frontend/src/stores/auth.js:53` | `logout()` 中 `sessionStore.sessions = {}` 直接赋值 ref 而非 `.value`，可能不触发响应 |
| 23 | `frontend/src/composables/useGraphController.js:49` | `relationColors` 是普通对象而非 reactive |
| 24 | 多个文件 | 大量 `console.log` 调试日志未清理（ChatView 18处、useGraphController 7处） |

---

## 修复优先级建议

```
第1批（清理死代码）：  #1, #3, #9
第2批（安全 + 内存）： #2, #4
第3批（逻辑修复）：    #5, #6, #7, #8, #10
第4批（改善）：        #11 ~ #24
```
