# RAG 系统优化任务清单

基于 RAGAS 评测驱动的系统调优计划。

## 工作流程

每项任务按以下流程推进：

1. **运行 RAGAS 评测**：用当前代码跑评测，记录基线指标
2. **修改代码**：实现优化方案
3. **再次评测**：跑同样的测试用例，对比指标变化
4. **真实测试**：用浏览器/Chrome 插件打开前端，实际发消息验证功能正常
5. **Git commit**：确认无误后提交，commit message 描述改动内容

## 状态说明

- `⬜ 待开始`：未开始
- `🔵 进行中`：正在推进
- `✅ 完成`：已完成，记录了评测结果
- `⏸️ 观察`：观察项，等待评测数据决定是否推进

**状态维护规则**：每项任务必须及时更新状态，确保任何时候读取 Task.md 都能了解当前进度。上下文压缩后通过读取 Task.md 恢复进度。

---

## 高优先级

### 1. Prompt 调优 ⬜ 待开始

**目标指标**：faithfulness ↑、answer_relevancy ↑
**理由**：成本最低，只改 prompt 文本，无需重建索引，见效最快

#### 1.1 加 few-shot 示例
- ⬜ 在 system prompt 中加入 2-3 个完整的"用户问 → 工具调用 → 最终回答"示例
- ⬜ 覆盖三种典型场景：数值查询(precise)、剧情查询(semantic)、关系查询(graphrag)
- ⬜ RAGAS 评测对比

#### 1.2 约束回答结构
- ⬜ 增加结构化回答约束（数值列具体数字、剧情标活动名、干员标星级职业）
- ⬜ RAGAS 评测对比

#### 1.3 分离 tool prompt 和 answer prompt
- ⬜ 工具调用完成后注入约束消息："基于以上检索结果回答，不要编造检索结果中没有的信息"
- ⬜ RAGAS 评测对比

**涉及文件**：`backend/agent/prompts.py`、`backend/agent/core.py`

---

### 2. 重排调参 ⬜ 待开始

**目标指标**：context_precision ↑
**理由**：只改参数不改结构，每组参数跑一次评测即可，无需重建索引

#### 2.1 Reranker top_n 实验
- ⬜ 测试 top_n = 3、5（当前）、8，记录 context_precision 变化

#### 2.2 候选数量实验
- ⬜ 测试送入 reranker 的候选数：top_k×3（当前 15）vs top_k×5（25）
- ⬜ 记录 context_precision 和 context_recall 的平衡点

#### 2.3 Reranker 分数阈值过滤
- ⬜ 对 reranker 的 relevance_score 设阈值，低于阈值的 chunk 不进入 parent document 扩展
- ⬜ 测试不同阈值（0.3、0.5、0.7）

**涉及文件**：`backend/agent/tool_implementations.py`、`backend/lc/reranker.py`

---

## 中优先级

### 3. search_mode 权重验证与调优 ⬜ 待开始

**目标指标**：context_recall ↑
**前置条件**：search_mode 功能已实现（✅），需要通过 RAGAS 评测验证效果并微调权重值

#### 3.1 评测 search_mode 效果
- ⬜ 用 precise/semantic/balanced 三种模式分别跑评测
- ⬜ 对比固定 0.5 权重 vs 动态权重的 context_recall 差异

#### 3.2 权重值微调
- ⬜ 根据评测结果调整 precise/semantic 的权重值（当前 0.25/0.75）
- ⬜ 可能的组合：0.2/0.8、0.3/0.7、0.15/0.85

**涉及文件**：`backend/agent/tool_implementations.py`、`backend/agent/prompts.py`

---

## 低优先级（观察项）

> 以下任务需要重建索引（chunker → BM25 → FAISS → embedding），成本高。仅在高/中优先级完成后 RAGAS 指标仍有明显短板时考虑。

### 4. Chunk 策略优化 ⏸️ 观察

**目标指标**：context_precision ↑ + context_recall ↑
**当前配置**：target_size=4000（匹配 bge-m3 的 8k 上下文长度的一半）
**暂缓理由**：当前 chunk size 已是合理选择，且有 Parent Document 扩展弥补上下文不足。重建全部索引成本高，收益不确定。

- ⬜ 如 context_precision/context_recall 指标不理想，测试 target_size = 2000 vs 6000
- ⬜ 每组需重建 BM25 + FAISS 索引

**涉及文件**：`backend/data/chunker.py`

### 5. Parent Document 扩展策略 ⏸️ 观察

**目标指标**：faithfulness ↑
**暂缓理由**：当前截断 2000 字的策略配合重排已能工作，只有在 faithfulness 指标偏低时才需调整

- ⬜ 如 faithfulness 偏低，测试关闭扩展 vs 当前 vs 截断 3000 的效果
- ⬜ 评估扩展是否引入过多无关内容

**涉及文件**：`backend/agent/tool_implementations.py`、`backend/rag/parent_document.py`

---

## 评测基线

首次评测时填写，后续每项优化完成后追加记录。

| 指标 | 说明 | 优化方向 |
|------|------|----------|
| context_precision | 召回文档中相关文档的占比 | 重排调参 |
| context_recall | 应该召回的文档被召回的比例 | search_mode 权重 |
| faithfulness | 回答是否忠于检索到的文档 | Prompt 调优 |
| answer_relevancy | 回答与问题的相关程度 | Prompt 调优 |

### 评测记录

| 日期 | 优化内容 | context_precision | context_recall | faithfulness | answer_relevancy | 测试用例数 | 备注 |
|------|---------|-------------------|----------------|--------------|------------------|-----------|------|
| — | 基线（当前代码） | — | — | — | — | — | 待首次评测 |
