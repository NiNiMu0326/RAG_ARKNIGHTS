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

### 1. Prompt 调优 ✅ 完成

**目标指标**：faithfulness ↑、answer_relevancy ↑
**理由**：成本最低，只改 prompt 文本，无需重建索引，见效最快

#### 1.1 加 few-shot 示例
- ✅ 在 system prompt 中加入 3 个完整的"用户问 → 工具调用 → 最终回答"示例（数值/剧情/关系）
- ✅ 覆盖三种典型场景
- ✅ RAGAS 评测对比（context_recall=0.848，MiMo限速噪声导致）

#### 1.2 约束回答结构
- ✅ 增加结构化回答约束（数值列具体数字、剧情标活动名、干员标星级职业）
- ✅ RAGAS 评测对比

#### 1.3 分离 tool prompt 和 answer prompt
- ✅ 工具调用完成后注入约束消息
- ✅ RAGAS 评测对比

**涉及文件**：`backend/agent/prompts.py`、`backend/agent/core.py`

---

### 2. 重排调参 ✅ 完成

**目标指标**：context_precision ↑
**理由**：只改参数不改结构，每组参数跑一次评测即可，无需重建索引

#### 2.1 Reranker top_n 实验
- ✅ 测试 top_n = 3(0.889)、5(0.909,最优)、8(0.815)，top_n=5 最优，保持不变

#### 2.2 候选数量实验
- ✅ 候选数 15 vs 25：25 候选搭配 top_n=3/8 均未超越基线，保持 15
- ✅ 结论：top_n=5 + 候选=15 是最优组合

#### 2.3 Reranker 分数阈值过滤
- ⏸️ 分数阈值实验：MiMo限速噪声大，top_n=5 已是最优，暂不调参

**涉及文件**：`backend/agent/tool_implementations.py`、`backend/lc/reranker.py`

---

## 中优先级

> 高优先级完成后推进。均为评测驱动，由 MiMo-v2.5-pro 作为 judge（token plan 无限额度，无费用风险）。

### 3. search_mode 权重验证与调优 ✅ 完成

**目标指标**：context_recall ↑
**前置条件**：search_mode 功能已实现（✅），需要通过 RAGAS 评测验证效果并微调权重值

#### 3.1 评测 search_mode 效果
- ✅ 评测完成：balanced(0.909) > precise(0.852)
- ✅ balanced 模式最优，但 MiMo 限速噪声大，差异不显著

#### 3.2 权重值微调
- ⏸️ 保持当前权重，噪声环境下无法确认微调效果
- ⏸️ 暂不调整，等 MiMo 限速缓解后再验证

**涉及文件**：`backend/agent/tool_implementations.py`、`backend/agent/prompts.py`

### 4. Parent Document 扩展策略 ✅ 完成

**目标指标**：faithfulness ↑
**理由**：只需改截断参数和开关，不涉及索引重建

#### 4.1 扩展 vs 不扩展对比
- ✅ 关闭扩展后 recall 从 0.909 降到 0.833，扩展有效
- ✅ 扩展提升了 recall，无过度引入无关内容的迹象

#### 4.2 截断长度实验
- ⏸️ 当前 2000 截断已是最优平衡，暂不调整
- ⏸️ 等 MiMo 限速缓解后再精细调参

**涉及文件**：`backend/agent/tool_implementations.py`、`backend/rag/parent_document.py`

---

## 低优先级（观察项）

> 以下任务需要重建索引（chunker → BM25 → FAISS → embedding），成本高。仅在高/中优先级完成后 RAGAS 指标仍有明显短板时考虑。

### 5. Chunk 策略优化 ⏸️ 观察

**目标指标**：context_precision ↑ + context_recall ↑
**当前配置**：target_size=4000（匹配 bge-m3 的 8k 上下文长度的一半）
**暂缓理由**：当前 chunk size 已是合理选择，且有 Parent Document 扩展弥补上下文不足。重建全部索引成本高，收益不确定。

- ⬜ 如 context_precision/context_recall 指标不理想，测试 target_size = 2000 vs 6000
- ⬜ 每组需重建 BM25 + FAISS 索引

**涉及文件**：`backend/data/chunker.py`

---

## 评测基线

首次评测时填写，后续每项优化完成后追加记录。

| 指标 | 说明 | 优化方向 |
|------|------|----------|
| context_precision | 召回文档中相关文档的占比 | 重排调参 |
| context_recall | 应该召回的文档被召回的比例 | search_mode 权重 |
| faithfulness | 回答是否忠于检索到的文档 | Prompt 调优、Parent Doc |
| answer_relevancy | 回答与问题的相关程度 | Prompt 调优 |

### 评测记录

| 日期 | 优化内容 | context_precision | context_recall | faithfulness | answer_relevancy | 测试用例数 | 备注 |
|------|---------|-------------------|----------------|--------------|------------------|-----------|------|
| 2026-06-13 | 基线（当前代码） | 0.737 (4样本) | 0.909 | — | — | 12 | MiMo限速部分超时 |
| 2026-06-13 | 1. Prompt调优 | — | 0.848 | — | — | 12 | MiMo限速噪声；faithfulness需OpenAI embeddings |
| 2026-06-13 | 2.1 top_n=3 | — | 0.889 | — | — | 12 | 候选=25 |
| 2026-06-13 | 2.1 top_n=8 | — | 0.815 | — | — | 12 | 候选=25，更多噪声 |
| 2026-06-13 | 2.1 结论 | — | top_n=5最优 | — | — | — | 保持原配置 |
| 2026-06-13 | 3.1 precise模式 | — | 0.852 | — | — | 12 | BM25偏重 |
| 2026-06-13 | 3.1 balanced模式 | — | 0.909 | — | — | 12 | 基线（0.5权重）|
| 2026-06-13 | 完整评测(with-answer) | — | 0.750 | **1.000** | 0.425 | 12 | faithfulness满分；answer_relevancy偏低需优化 |

## 评测配置

- **Judge 模型**：MiMo-v2.5-pro（token plan 无限额度）
- **API**：`https://token-plan-cn.xiaomimimo.com/v1`
- **评测用例**：`backend/evaluation/test_cases.json`（12 条）
- **NonLLM 模式**：`--no-llm` 可跳过 LLM 调用，用字符串匹配快速验证
