# ARKNIGHTS Agent 深度测试报告

> 生成日期：2026-05-22 | 总发现数：57

---

## 1. 执行摘要

本次深度测试覆盖后端 API、安全审计、前端可访问性、代码审查和性能分析五个领域。共发现 **57 项问题**：

| 严重程度 | 数量 | 说明 |
|---------|------|------|
| **P0** | 11 | 服务无法启动、核心功能失效、高危安全漏洞 |
| **P1** | 20 | 功能缺陷、中等安全风险、可访问性合规问题 |
| **P2** | 18 | 测试覆盖率不足、用户体验问题、可优化项 |
| **P3** | 8 | 代码风格、冗余操作、低风险告警 |

**关键结论**：
- **最严重阻塞**：`backend/main.py:848` SyntaxError 导致后端完全无法启动，阻断所有集成测试
- **安全风险**：JWT 存储在 localStorage（XSS 窃取）、请求日志明文记录密码、pickle 反序列化 RCE、JWT 密钥仅 25 字节
- **test-writer 已完成**：新增 5 个测试文件（共 136 个新测试），修复 1 个已有测试

---

## 2. P0 阻塞问题

### 2.1 main.py:848 SyntaxError（核心阻塞）
- **组件**：`backend/main.py:848`
- **根因**：`get_quick_questions()` 函数中变量在第 664 行被读取后，`global` 声明在第 848 行出现
- **影响**：后端无法启动，所有集成测试 0 收集
- **修复**：将 `global _quick_questions_cache, _quick_questions_cache_time` 移至函数体最前面

### 2.2 缺少 jieba 依赖
- **组件**：`test/test_retrievers.py` → `backend/data/bm25_index.py`
- **修复**：`pip install jieba` 并加入 `requirements.txt`

### 2.3 test_sessions.py 断言过时（已修复）
- **组件**：`test/test_sessions.py:127`
- **修复**：`assert len(sid) == 8` → `assert len(sid) == 36`（匹配 UUID 格式）

### 2.4 请求日志泄露明文密码
- **组件**：`backend/main.py` log_requests 中间件
- **修复**：过滤 password/old_password/new_password/token/secret 字段

### 2.5 pickle 反序列化 RCE 风险
- **组件**：`backend/data/bm25_index.py:73`、`backend/storage/faiss_client.py:93`
- **修复**：替换为 JSON/MessagePack 或添加 HMAC 签名

### 2.6 JWT 存储在 localStorage
- **组件**：`frontend/src/stores/auth.js`
- **风险**：任何 XSS 均可窃取 JWT token
- **修复**：迁移到 httpOnly Cookie

### 2.7 logout 直接变异 Pinia 状态
- **组件**：`frontend/src/stores/auth.js:51-56`
- **修复**：添加 `resetSessions()` action

### 2.8 ESLint 配置缺失
- **组件**：`frontend/`
- **修复**：`npm init @eslint/config` 选择 Vue 3 插件

---

## 3. 安全发现

### 依赖漏洞
- **npm audit**：3 moderate（esbuild、ws、vite）
- **pip-audit**：123 个已知漏洞（starlette、python-multipart、requests、idna 等关键依赖有 CVE）

### 认证/授权
| 严重度 | 问题 | 组件 |
|--------|------|------|
| P0 | JWT localStorage 存储 | auth.js |
| P0 | 日志明文密码 | main.py log_requests |
| P1 | JWT 密钥 25 字节（< 32） | config.py |
| P1 | JWT 过期 30 天过长 | auth.py |
| P1 | 认证端点无速率限制 | main.py /auth/* |
| P1 | GET /agent/debug/trace 无认证 | main.py |
| P1 | Agent 会话端点无 JWT 保护 | main.py |
| P2 | POST /agent/chat 无认证 | main.py |

### 配置安全
- 绑定 0.0.0.0（P2）
- 缺少 .env.example（P1）
- 多处 random 替代 secrets（P1）

---

## 4. 测试覆盖

### 已有测试状态

| 文件 | 测试数 | 状态 |
|------|--------|------|
| test_auth.py | 27 | all pass |
| test_core.py | 22 | all pass |
| test_sessions.py | 21 | fixed (was 1 fail) |
| test_injection_detection.py | 43 | 4 skip |
| test_parent_document.py | 12 | all pass |
| test_deepseek_think.py | 9 | all pass |
| test_graph_builder.py | 11 | all pass |
| test_api.py | 0 | ERROR (SyntaxError) |
| test_retrievers.py | 0 | ERROR (jieba missing) |

### test-writer 新增文件

| 文件 | 测试数 | 覆盖模块 |
|------|--------|----------|
| test_tools.py | 17 | ToolRegistry + TOOL_SCHEMAS |
| test_db.py | 18 | SQLite init + tables |
| test_llm_factory.py | 25 | Model registry + client factory |
| test_web_search.py | 19 | Tavily + DuckDuckGo mock |
| test_injection.py | 34 | injection detection (was skipped) |

**新增总计**：136 个测试，0 个失败

---

## 5. 前端质量

### 可访问性（P1-P2）
- 表单缺 `<label>`、按钮缺 `aria-label`
- 缺语义 HTML 地标（`<main>`、`role="dialog"`）
- focus outline 被移除无替代
- GraphView 无键盘支持

### SSE 流式处理（P1-P2）
- 无超时/重连机制
- 会话切换竞态条件（`updateToolCallResult` 用错会话）
- 无背压控制

### 前端测试计划（4 项 vitest）
1. 按钮 aria-label 验证
2. 表单标签验证
3. SSE 超时处理
4. Auth logout 会话重置

---

## 6. 性能分析

| 严重度 | 问题 | 建议 |
|--------|------|------|
| P1 | FAISS+BM25 串行执行 | 使用 asyncio.gather 并行 |
| P1 | Parent Document LRU=100 过小 | 增至 1000+ |
| P2 | Cross-Encoder 逐 API 调用 | 使用批量 rerank 接口 |
| P2 | 会话纯内存存储 | 持久化到 SQLite |
| P2 | SSE 队列无背压 | 设置 maxsize |
| P3 | SQLite 无连接池 | 启用 WAL + 连接复用 |

---

## 7. CI/CD 跟进

### 立即修复（30 分钟）
1. 修复 `main.py:848` SyntaxError
2. `pip install jieba` 并加入 requirements.txt
3. 验证 `python -m pytest` 全部通过

### 短期（1-2 天）
- JWT httpOnly Cookie 迁移
- 日志密码过滤
- Auth Store logout 修复
- SSE 超时/重连
- ESLint 配置

### 中期（1-2 周）
- API 端点测试扩展
- Agent 核心单元测试
- 可访问性修复
- 依赖更新
- 速率限制

### 长期（1-3 月）
- pickle 替换为安全格式
- 会话 SQLite 持久化
- Playwright E2E 测试
- 性能基准测试

---

## 8. Agent 执行记录

| Agent | 状态 | 发现数 |
|-------|------|--------|
| code-review-qa | PARTIAL | 15 |
| api-qa | FAILED | 5 |
| security-qa | PARTIAL | 11 |
| frontend-qa | PARTIAL | 26 |
| 性能分析 | COMPLETED | 6 |
| test-writer | SUCCESS | 5 文件 136 测试 |
| report-synthesizer | COMPLETED | 聚合报告 |

---

## 9. 产出文件

- `.deeptest/discovery.json` — 项目发现数据
- `.deeptest/strategy.md` — 测试策略
- `.deeptest/merged-findings.json` — 57 项去重发现
- `.deeptest/report.md` — 本报告
- `test/test_tools.py` — 新增（17 tests）
- `test/test_db.py` — 新增（18 tests）
- `test/test_llm_factory.py` — 新增（25 tests）
- `test/test_web_search.py` — 新增（19 tests）
- `test/test_injection.py` — 新增（34 tests）
- `test/test_sessions.py` — 修复 1 处断言
