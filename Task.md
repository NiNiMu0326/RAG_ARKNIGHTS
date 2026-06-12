# RAG 系统优化任务清单

基于 RAGAS 评测驱动的系统调优计划。每项任务完成后标记 `[x]`，记录实际指标变化。

---

## 1. Prompt 调优

**目标指标**：faithfulness ↑、answer_relevancy ↑  
**优先级**：最高（成本最低、见效最快）

### 1.1 加 few-shot 示例
- [ ] 在 system prompt 中加入 2-3 个完整的"用户问 → 工具调用 → 最终回答"示例
- [ ] 覆盖三种典型场景：数值查询、剧情查询、关系查询
- [ ] 评测 RAGAS 指标变化

### 1.2 约束回答结构
- [ ] 在 prompt 中增加结构化回答约束，例如：
  - "涉及数值时必须列出具体数字"
  - "涉及剧情时标注活动/章节名"
  - "涉及干员时注明星级和职业"
- [ ] 评测 faithfulness 变化

### 1.3 分离 tool prompt 和 answer prompt
- [ ] 在工具调用完成后、最终回答前，注入一条约束消息：
  - "基于以上检索结果回答，不要编造检索结果中没有的信息"
- [ ] 评测 faithfulness 和 answer_relevancy 变化

**文件**：`backend/agent/prompts.py`、`backend/agent/core.py`

---

## 2. 重排调参

**目标指标**：context_precision ↑  
**优先级**：高

### 2.1 Reranker top_n 实验
- [ ] 测试 top_n = 3、5、8，记录 context_precision 变化

### 2.2 候选数量实验
- [ ] 测试送入 reranker 的候选数：top_k×3（当前 15）vs top_k×5（25）
- [ ] 记录 context_precision 和 context_recall 的平衡点

### 2.3 Reranker 分数阈值过滤
- [ ] 对 reranker 返回的 relevance_score 设阈值，低于阈值的 chunk 不进入 parent document 扩展
- [ ] 测试不同阈值（0.3、0.5、0.7）的效果

**文件**：`backend/agent/tool_implementations.py`、`backend/lc/reranker.py`

---

## 3. BM25/向量权重调优

**目标指标**：context_recall ↑  
**优先级**：中高

### 3.1 按查询类型动态调权
- [ ] 在 Agent tool schema 中增加可选参数 `search_mode`（如 `precise` / `semantic`）
- [ ] `precise` 模式：vector_weight 偏低（如 0.3），侧重 BM25 关键词匹配
- [ ] `semantic` 模式：vector_weight 偏高（如 0.7），侧重向量语义匹配
- [ ] 评测不同类型 query 的 context_recall 变化

**文件**：`backend/agent/tools.py`、`backend/rag/retrievers.py`、`backend/agent/tool_implementations.py`

---

## 4. Chunk 策略优化

**目标指标**：context_precision ↑ + context_recall ↑  
**优先级**：中

### 4.1 Chunk 大小实验
- [ ] 测试 target_size = 2000 vs 4000（当前）vs 6000
- [ ] 每组重新构建 BM25 索引和 FAISS 索引
- [ ] 记录 context_precision 和 context_recall 的变化趋势
- [ ] 找到最优 target_size

### 4.2 最小 chunk 大小实验
- [ ] 测试 min_size = 800 vs 1500（当前）vs 2000
- [ ] 评估过小 chunk 对语义集中度的影响

**文件**：`backend/data/chunker.py`  
**注意**：chunk 策略变更后需要重建所有索引（BM25 + FAISS）

---

## 5. Parent Document 扩展策略

**目标指标**：faithfulness ↑、answer_relevancy ↑  
**优先级**：中

### 5.1 扩展 vs 不扩展对比
- [ ] 关闭 parent document 扩展，评测 faithfulness 和 answer_relevancy 变化
- [ ] 评估扩展是否引入了过多无关内容导致幻觉

### 5.2 截断长度实验
- [ ] 测试 content 截断长度：1000 vs 2000（当前）vs 3000
- [ ] 评估截断过短是否丢失关键信息、过长是否稀释答案

**文件**：`backend/agent/tool_implementations.py`、`backend/rag/parent_document.py`

---

## 评测基线

每项优化前后都用 RAGAS 记录以下指标（同一组测试用例）：

| 指标 | 说明 | 优化方向 |
|------|------|----------|
| context_precision | 召回的文档中相关文档的占比 | 重排、chunk 策略 |
| context_recall | 应该召回的文档被召回的比例 | BM25/向量权重、chunk 策略 |
| faithfulness | 回答内容是否忠于检索到的文档 | prompt 调优、parent doc 扩展 |
| answer_relevancy | 回答与问题的相关程度 | prompt 调优 |

**当前基线值**：待首次评测填写

| 指标 | 基线值 | 测试用例数 | 日期 |
|------|--------|-----------|------|
| context_precision | — | — | — |
| context_recall | — | — | — |
| faithfulness | — | — | — |
| answer_relevancy | — | — | — |
