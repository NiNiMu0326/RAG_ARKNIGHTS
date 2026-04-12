"""
RAG Evaluation Module - 完整评估系统
评估指标：
1. 检索指标：召回率、准确率、F1@K
2. 生成指标：ROUGE、LLM 质量评估
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
import math

try:
    from backend.api.siliconflow import SiliconFlowClient
    import backend.config as config
    SILICONFLOW_AVAILABLE = True
except ImportError:
    SILICONFLOW_AVAILABLE = False
    config = None


# ============== 检索评估指标 ==============

def calculate_recall_at_k(
    retrieved_ids: List[str],
    expected_ids: List[str],
    k: int = 5
) -> float:
    """
    计算召回率 @K
    Recall@K = |relevant_docs ∩ retrieved_docs| / |relevant_docs|
    支持前缀匹配（如 expected="operators_0015" 匹配 "operators_0015_01"）
    """
    retrieved_k = retrieved_ids[:k]
    expected = expected_ids
    
    if not expected:
        return 0.0
    
    # 计算匹配的文档数
    matched = 0
    for exp in expected:
        for ret in retrieved_k:
            # 精确匹配或前缀匹配
            if ret == exp or ret.startswith(exp + "_") or exp.startswith(ret + "_"):
                matched += 1
                break
    
    return matched / len(expected)


def calculate_precision_at_k(
    retrieved_ids: List[str],
    expected_ids: List[str],
    k: int = 5
) -> float:
    """
    计算准确率 @K
    Precision@K = |relevant_docs ∩ retrieved_docs| / K
    支持前缀匹配
    """
    retrieved_k = retrieved_ids[:k]
    expected = expected_ids
    
    if k == 0:
        return 0.0
    
    matched = 0
    for ret in retrieved_k:
        for exp in expected:
            if ret == exp or ret.startswith(exp + "_") or exp.startswith(ret + "_"):
                matched += 1
                break
    
    return matched / k


def calculate_f1_at_k(
    retrieved_ids: List[str],
    expected_ids: List[str],
    k: int = 5
) -> float:
    """计算 F1@K"""
    precision = calculate_precision_at_k(retrieved_ids, expected_ids, k)
    recall = calculate_recall_at_k(retrieved_ids, expected_ids, k)
    
    if precision + recall == 0:
        return 0.0
    
    return 2 * (precision * recall) / (precision + recall)


def calculate_mrr(retrieved_ids: List[str], expected_ids: List[str]) -> float:
    """
    计算平均倒数排名 (Mean Reciprocal Rank)
    MRR = 1 / |Q| * Σ(1 / rank_i)
    支持前缀匹配
    """
    expected = expected_ids
    
    for i, doc_id in enumerate(retrieved_ids, 1):
        for exp in expected:
            if doc_id == exp or doc_id.startswith(exp + "_") or exp.startswith(doc_id + "_"):
                return 1.0 / i
    
    return 0.0


def calculate_ndcg_at_k(
    retrieved_ids: List[str],
    expected_ids: List[str],
    k: int = 5
) -> float:
    """
    计算 NDCG@K (Normalized Discounted Cumulative Gain)
    支持前缀匹配
    """
    expected = expected_ids
    
    # DCG = Σ(rel_i / log2(i+1))
    dcg = 0.0
    for i, doc_id in enumerate(retrieved_ids[:k], 1):
        rel = 0.0
        for exp in expected:
            if doc_id == exp or doc_id.startswith(exp + "_") or exp.startswith(doc_id + "_"):
                rel = 1.0
                break
        dcg += rel / math.log2(i + 1)
    
    # IDCG = ideal DCG
    idcg = 0.0
    for i in range(1, min(len(expected), k) + 1):
        idcg += 1.0 / math.log2(i + 1)
    
    if idcg == 0:
        return 0.0
    
    return dcg / idcg


# ============== 生成评估指标 ==============

def calculate_rouge(
    reference: str,
    hypothesis: str
) -> Dict[str, float]:
    """
    计算 ROUGE 指标 (Recall-Oriented Understudy for Gisting Evaluation)
    - ROUGE-1: unigram overlap (单词级别)
    - ROUGE-2: bigram overlap (词对级别)
    - ROUGE-L: longest common subsequence
    """
    ref_tokens = reference.lower().split()
    hyp_tokens = hypothesis.lower().split()
    
    def rouge_n(n: int) -> float:
        """ROUGE-N: n-gram overlap"""
        if not ref_tokens or not hyp_tokens:
            return 0.0
        
        ref_ngrams = Counter(tuple(ref_tokens[i:i+n]) for i in range(len(ref_tokens)-n+1))
        hyp_ngrams = Counter(tuple(hyp_tokens[i:i+n]) for i in range(len(hyp_tokens)-n+1))
        
        overlap = sum((ref_ngrams & hyp_ngrams).values())
        total = sum(ref_ngrams.values())
        
        return overlap / total if total > 0 else 0.0
    
    def rouge_l() -> float:
        """ROUGE-L: LCS based"""
        if not ref_tokens or not hyp_tokens:
            return 0.0
        
        m, n = len(ref_tokens), len(hyp_tokens)
        # 简化的 LCS 计算
        dp = [[0] * (n + 1) for _ in range(2)]
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if ref_tokens[i-1] == hyp_tokens[j-1]:
                    dp[i % 2][j] = dp[(i-1) % 2][j-1] + 1
                else:
                    dp[i % 2][j] = max(dp[(i-1) % 2][j], dp[i % 2][j-1])
        
        lcs_length = dp[m % 2][n]
        return lcs_length / m if m > 0 else 0.0
    
    return {
        "rouge_1": round(rouge_n(1), 4),
        "rouge_2": round(rouge_n(2), 4),
        "rouge_l": round(rouge_l(), 4)
    }


def calculate_keyword_coverage(
    answer: str,
    expected_keywords: List[str]
) -> Dict[str, Any]:
    """计算关键词覆盖率"""
    if not answer or not expected_keywords:
        return {
            "coverage": 0.0,
            "found_keywords": [],
            "missing_keywords": expected_keywords or []
        }
    
    answer_lower = answer.lower()
    found = [kw for kw in expected_keywords if kw.lower() in answer_lower]
    missing = [kw for kw in expected_keywords if kw.lower() not in answer_lower]
    
    return {
        "coverage": round(len(found) / len(expected_keywords), 4),
        "found_keywords": found,
        "missing_keywords": missing
    }


# ============== LLM 评估 ==============

def _extract_json_from_response(response: str) -> Dict[str, Any]:
    """从 LLM 响应中提取 JSON，支持 markdown 代码块包裹"""
    # 尝试直接解析
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass
    
    # 尝试提取 ```json ... ``` 代码块
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # 尝试提取花括号内容
    brace_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass
    
    # 解析失败
    raise ValueError(f"Cannot extract JSON from response: {response[:200]}")

class LLMEvaluator:
    """
    LLM-based judge for evaluating RAG answers
    评估维度：
    1. 检索召回 - 文档是否相关
    2. 答案相关性 - 是否针对问题
    3. 答案准确性 - 内容是否正确
    4. 答案完整性 - 是否完整回答
    """

    JUDGE_PROMPT = """你是一个严格的RAG系统评估员。请评估以下问答对中，AI助手的回答质量。

问题：{question}
AI助手回答：{answer}
参考答案：{reference}

请从以下四个维度评分（每个维度1-10分，保留一位小数）：
1. 检索召回(4分权重)：文档是否涵盖了问题的关键信息
2. 答案相关性(3分权重)：回答是否针对问题，没有偏题
3. 答案准确性(3分权重)：回答内容是否正确，与参考答案一致

请以JSON格式返回评分结果：
{{
    "retrieval_relevance": 分数(1-10),
    "answer_relevance": 分数(1-10),
    "answer_accuracy": 分数(1-10),
    "reasoning": "评分理由（50字以内）"
}}

只返回JSON，不要包含其他文字。"""

    def __init__(self, api_key: str, eval_model: str = None):
        self.api_key = api_key
        self.client = SiliconFlowClient(api_key) if SILICONFLOW_AVAILABLE else None
        # 使用 SiliconFlow 上的 DeepSeek-V3 进行评估
        self.eval_model = eval_model or 'deepseek-ai/DeepSeek-V3'

    def evaluate(self, question: str, answer: str, reference: str = "", 
                expected_keywords: List[str] = None) -> Dict[str, Any]:
        """
        完整评估：关键词覆盖 + ROUGE + LLM评估
        """
        results = {
            "success": True,
            "llm_scores": None
        }
        
        # 1. 关键词覆盖
        keyword_info = calculate_keyword_coverage(answer, expected_keywords or [])
        results["keyword_coverage"] = keyword_info["coverage"]
        results["found_keywords"] = keyword_info["found_keywords"]
        results["missing_keywords"] = keyword_info["missing_keywords"]
        
        # 2. ROUGE
        if reference:
            rouge_scores = calculate_rouge(reference, answer)
            results["rouge"] = rouge_scores
        else:
            results["rouge"] = {"rouge_1": 0, "rouge_2": 0, "rouge_l": 0}
        
        # 3. LLM 评估（即使没有参考答案也可评估相关性）
        if self.client:
            try:
                prompt = self.JUDGE_PROMPT.format(
                    question=question,
                    answer=answer if answer else "(无回答)",
                    reference=reference if reference else "(无参考答案，请根据知识判断准确性)"
                )
                
                response = self.client.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.eval_model,
                    temperature=0.1
                )
                
                # 尝试从响应中提取 JSON
                llm_scores = _extract_json_from_response(response)
                
                # 验证分数范围
                for key in ["retrieval_relevance", "answer_relevance", "answer_accuracy"]:
                    score = llm_scores.get(key, 6.0)
                    llm_scores[key] = max(1.0, min(10.0, float(score)))
                
                results["llm_scores"] = llm_scores
                results["llm_reasoning"] = llm_scores.get("reasoning", "")
                
            except Exception as e:
                results["llm_error"] = str(e)
                results["llm_scores"] = {
                    "retrieval_relevance": 0,
                    "answer_relevance": 0,
                    "answer_accuracy": 0,
                    "reasoning": f"评估失败: {e}"
                }
        else:
            results["llm_scores"] = {
                "retrieval_relevance": 0,
                "answer_relevance": 0,
                "answer_accuracy": 0,
                "reasoning": "无LLM评估（缺少API）"
            }
        
        return results


# ============== 评估结果类 ==============

class EvaluationResult:
    """单条评估结果"""
    
    def __init__(
        self,
        question_id: int,
        question: str,
        answer: str,
        retrieved_docs: Optional[List[str]] = None,
        expected_docs: Optional[List[str]] = None,
        details: Optional[Dict] = None,
        error: Optional[str] = None
    ):
        self.question_id = question_id
        self.question = question
        self.answer = answer
        self.retrieved_docs = retrieved_docs or []
        self.expected_docs = expected_docs or []
        self.details = details or {}
        self.error = error
        
        # 计算综合分数
        self._compute_scores()
    
    def _compute_scores(self):
        """计算各项分数"""
        # 检索指标
        self.recall_5 = calculate_recall_at_k(self.retrieved_docs, self.expected_docs, 5)
        self.precision_5 = calculate_precision_at_k(self.retrieved_docs, self.expected_docs, 5)
        self.f1_5 = calculate_f1_at_k(self.retrieved_docs, self.expected_docs, 5)
        self.mrr = calculate_mrr(self.retrieved_docs, self.expected_docs)
        self.ndcg_5 = calculate_ndcg_at_k(self.retrieved_docs, self.expected_docs, 5)
        
        # 生成指标
        llm_scores = self.details.get("llm_scores", {})
        self.retrieval_relevance = llm_scores.get("retrieval_relevance", 0)
        self.answer_relevance = llm_scores.get("answer_relevance", 0)
        self.answer_accuracy = llm_scores.get("answer_accuracy", 0)
        
        # 综合分数 = LLM 三维度加权平均
        # 检索召回(4) + 答案相关性(3) + 答案准确性(3) = 10
        if self.retrieval_relevance > 0 or self.answer_relevance > 0 or self.answer_accuracy > 0:
            self.overall_score = (
                self.retrieval_relevance * 0.4 +
                self.answer_relevance * 0.3 +
                self.answer_accuracy * 0.3
            )
        else:
            self.overall_score = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "question_id": self.question_id,
            "question": self.question,
            "answer": self.answer[:500] + "..." if len(self.answer) > 500 else self.answer,
            "retrieved_docs": self.retrieved_docs[:5],
            "expected_docs": self.expected_docs,
            # 检索指标
            "recall_5": round(self.recall_5 * 10, 2),
            "precision_5": round(self.precision_5 * 10, 2),
            "f1_5": round(self.f1_5 * 10, 2),
            "mrr": round(self.mrr * 10, 2),
            "ndcg_5": round(self.ndcg_5 * 10, 2),
            # 生成指标
            "retrieval_relevance": self.retrieval_relevance,
            "answer_relevance": self.answer_relevance,
            "answer_accuracy": self.answer_accuracy,
            # 综合
            "overall_score": round(self.overall_score, 2),
            # 详情
            "keyword_coverage": self.details.get("keyword_coverage", 0),
            "rouge": self.details.get("rouge", {}),
            "llm_reasoning": self.details.get("llm_reasoning", ""),
            "error": self.error
        }


# ============== 评估运行函数 ==============

def load_questions(questions_file: Path) -> List[Dict[str, Any]]:
    """加载问题列表"""
    with open(questions_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("questions", [])


def run_evaluation(
    questions: List[Dict[str, Any]],
    rag_pipeline_fn,
    evaluator: Optional[LLMEvaluator] = None,
    progress_callback=None,
    api_key: str = None
) -> Dict[str, Any]:
    """
    运行完整评估
    
    Args:
        questions: 问题列表
        rag_pipeline_fn: RAG管道函数，输入question，输出 {"answer": str, "retrieved_docs": [str]}
        evaluator: LLM评估器（可选）
        progress_callback: 进度回调函数
    
    Returns:
        评估结果汇总
    """
    results = []
    total = len(questions)
    
    # 如果没有提供 evaluator 但提供了 api_key，创建 evaluator
    if not evaluator and api_key:
        evaluator = LLMEvaluator(api_key)
    
    for i, q in enumerate(questions):
        try:
            # 获取 RAG 回答和检索结果
            rag_result = rag_pipeline_fn(q["question"])
            answer = rag_result.get("answer", "")
            retrieved_docs = rag_result.get("retrieved_docs", [])
            
            # 获取期望文档
            expected_docs = q.get("expected_docs", [])
            expected_keywords = q.get("expected_keywords", [])
            reference = q.get("reference_answer", "")
            
            # 评估
            eval_details = {}
            if evaluator:
                eval_details = evaluator.evaluate(
                    question=q["question"],
                    answer=answer,
                    reference=reference,
                    expected_keywords=expected_keywords
                )
            
            results.append(EvaluationResult(
                question_id=q["id"],
                question=q["question"],
                answer=answer,
                retrieved_docs=retrieved_docs,
                expected_docs=expected_docs,
                details=eval_details
            ))
            
        except Exception as e:
            results.append(EvaluationResult(
                question_id=q.get("id", i + 1),
                question=q.get("question", ""),
                answer="",
                error=str(e)
            ))
        
        if progress_callback:
            progress_callback(i + 1, total)
    
    # 计算汇总统计
    successful = [r for r in results if not r.error]
    
    if successful:
        summary = {
            "total_questions": total,
            "evaluated": len(successful),
            "failed": len(results) - len(successful),
            # 检索指标汇总
            "retrieval": {
                "avg_recall_5": round(sum(r.recall_5 for r in successful) / len(successful) * 10, 2),
                "avg_precision_5": round(sum(r.precision_5 for r in successful) / len(successful) * 10, 2),
                "avg_f1_5": round(sum(r.f1_5 for r in successful) / len(successful) * 10, 2),
                "avg_mrr": round(sum(r.mrr for r in successful) / len(successful) * 10, 2),
                "avg_ndcg_5": round(sum(r.ndcg_5 for r in successful) / len(successful) * 10, 2),
            },
            # 生成指标汇总
            "generation": {
                "avg_retrieval_relevance": round(sum(r.retrieval_relevance for r in successful) / len(successful), 2),
                "avg_answer_relevance": round(sum(r.answer_relevance for r in successful) / len(successful), 2),
                "avg_answer_accuracy": round(sum(r.answer_accuracy for r in successful) / len(successful), 2),
            },
            # 综合分数
            "overall": {
                "avg_score": round(sum(r.overall_score for r in successful) / len(successful), 2),
            }
        }
    else:
        summary = {
            "total_questions": total,
            "evaluated": 0,
            "failed": total,
            "error": "所有评估均失败"
        }
    
    return {
        "summary": summary,
        "results": [r.to_dict() for r in results]
    }


# ============== 便捷函数 ==============

def quick_evaluate(
    question: str,
    answer: str,
    retrieved_docs: List[str],
    expected_docs: List[str],
    reference: str = "",
    api_key: str = None
) -> Dict[str, Any]:
    """
    快速评估单个问答对
    """
    if api_key:
        evaluator = LLMEvaluator(api_key)
        details = evaluator.evaluate(question, answer, reference)
    else:
        details = {}
    
    result = EvaluationResult(
        question_id=0,
        question=question,
        answer=answer,
        retrieved_docs=retrieved_docs,
        expected_docs=expected_docs,
        details=details
    )
    
    return result.to_dict()


def generate_report(evaluation_result: Dict[str, Any]) -> str:
    """
    生成文本评估报告
    """
    summary = evaluation_result.get("summary", {})
    
    report = f"""
# RAG 评估报告

## 概览
- 总问题数：{summary.get('total_questions', 0)}
- 成功评估：{summary.get('evaluated', 0)}
- 评估失败：{summary.get('failed', 0)}

## 检索指标 (满分10分)
| 指标 | 分数 |
|------|------|
| 召回率 @5 | {summary.get('retrieval', {}).get('avg_recall_5', 0):.2f} |
| 准确率 @5 | {summary.get('retrieval', {}).get('avg_precision_5', 0):.2f} |
| F1 @5 | {summary.get('retrieval', {}).get('avg_f1_5', 0):.2f} |
| MRR | {summary.get('retrieval', {}).get('avg_mrr', 0):.2f} |
| NDCG @5 | {summary.get('retrieval', {}).get('avg_ndcg_5', 0):.2f} |

## 生成指标 (满分10分)
| 指标 | 分数 |
|------|------|
| 检索相关性 | {summary.get('generation', {}).get('avg_retrieval_relevance', 0):.2f} |
| 答案相关性 | {summary.get('generation', {}).get('avg_answer_relevance', 0):.2f} |
| 答案准确性 | {summary.get('generation', {}).get('avg_answer_accuracy', 0):.2f} |

## 综合评分
**总分：{summary.get('overall', {}).get('avg_score', 0):.2f} / 10**

"""
    return report
