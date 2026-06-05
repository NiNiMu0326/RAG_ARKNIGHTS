# DeepTest 测试策略

## 项目概况
- 类型：web-app, api-service
- 语言：python, javascript
- 框架：Vite, Vue 3, FastAPI, Uvicorn
- 复杂度：medium
- 已有测试：10 个测试文件 (pytest)

## P0 - 必须测试

- **单元测试** — 核心业务逻辑函数
  - 工具：pytest, jest, vitest
- **集成测试** — API 端点和模块间调用
  - 工具：pytest + httpx, jest + supertest
- **安全测试** — 认证、授权、输入验证、依赖漏洞
  - 工具：bandit, safety, npm audit
  - 备注：有用户输入/JWT认证，提升安全测试优先级

## P1 - 建议测试

- **端到端测试** — 关键用户流程、页面导航
  - 工具：playwright, cypress
- **性能测试** — API 响应时间、吞吐量
  - 工具：locust, pytest-benchmark, k6, artillery
  - 备注：README/文档提及性能要求，提升性能测试优先级

## P2 - 可选测试

- **压力测试** — 并发请求、高负载稳定性
  - 工具：k6, wrk
- **兼容性测试** — 跨浏览器/设备/系统
  - 工具：cross-browser testing
- **可访问性测试** — WCAG 标准、键盘导航
  - 工具：axe-core, lighthouse

## Agent 派发计划

根据项目特征 (web-app + api-service)，Phase 1 将派发 4 个 Agent：

| Agent | 范围 | 优先级 | 需服务 |
|-------|------|--------|--------|
| code-review-qa | 静态分析 + 单元测试覆盖审查 | P0 | 否 |
| api-qa | API 端点验证、Schema 一致性、认证检查 | P0 | 是 |
| security-qa | 依赖漏洞扫描 + 代码安全分析 | P1 | 否 |
| frontend-qa | 浏览器端到端测试 + 可访问性审查 | P1 | 是 |

Phase 2（Phase 1 完成后串行）：
| Agent | 范围 | 优先级 |
|-------|------|--------|
| test-writer | 将发现转化为可复用测试文件 | P1 |
| report-synthesizer | 聚合发现、去重、生成最终测试报告 | P0 |
