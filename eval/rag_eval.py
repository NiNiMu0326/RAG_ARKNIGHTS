"""
RAG Evaluation Module
Uses LLM judge to evaluate RAG answer quality
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

# Try to import siliconflow for LLM calls
try:
    from backend.api.siliconflow import SiliconFlowClient
    SILICONFLOW_AVAILABLE = True
except ImportError:
    SILICONFLOW_AVAILABLE = False


class LLMEvaluator:
    """LLM-based judge for evaluating RAG answers"""

    JUDGE_PROMPT = """你是一个严格的RAG系统评估员。请评估以下问答对中，AI助手的回答质量。

问题：{question}
期望答案包含关键词：{keywords}
AI助手回答：{answer}

请从以下三个维度评分（每个维度1-10分，支持一位小数）：
1. 相关性：回答是否针对问题
2. 准确性：回答内容是否正确
3. 完整性：回答是否足够完整

请以JSON格式返回评分结果：
{{
    "relevance": 分数(1-10, 一位小数),
    "accuracy": 分数(1-10, 一位小数),
    "completeness": 分数(1-10, 一位小数),
    "overall": 综合分数(1-10, 一位小数),
    "reasoning": "评分理由简述"
}}

只返回JSON，不要包含其他文字。"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = SiliconFlowClient(api_key) if SILICONFLOW_AVAILABLE else None

    def evaluate(self, question: str, answer: str, expected_keywords: List[str]) -> Dict[str, Any]:
        """Evaluate a single RAG answer"""
        if not self.client:
            # Fallback: keyword-based scoring
            return self._keyword_evaluate(answer, expected_keywords)

        keywords_str = "、".join(expected_keywords)
        prompt = self.JUDGE_PROMPT.format(
            question=question,
            keywords=keywords_str,
            answer=answer if answer else "(无回答)"
        )

        try:
            response = self.client.chat(
                messages=[
                    {"role": "user", "content": prompt}
                ],
                model="qwen/qwen2.5-7b-instruct",
                temperature=0.1
            )

            # Parse JSON response
            result = json.loads(response)

            # Helper to clamp and round score
            def process_score(score, default=6.0):
                try:
                    s = float(score)
                    s = max(1.0, min(10.0, s))  # Clamp to 1-10
                    return round(s, 1)
                except (ValueError, TypeError):
                    return round(default, 1)

            relevance = process_score(result.get("relevance"), 6.0)
            accuracy = process_score(result.get("accuracy"), 6.0)
            completeness = process_score(result.get("completeness"), 6.0)
            overall = process_score(result.get("overall"), 6.0)

            return {
                "relevance": relevance,
                "accuracy": accuracy,
                "completeness": completeness,
                "overall": overall,
                "reasoning": result.get("reasoning", ""),
                "evaluation_method": "llm",
                "success": True
            }
        except Exception as e:
            return self._keyword_evaluate(answer, expected_keywords)

    def _keyword_evaluate(self, answer: str, expected_keywords: List[str]) -> Dict[str, Any]:
        """Fallback keyword-based evaluation"""
        if not answer:
            return {
                "relevance": 1.0,
                "accuracy": 1.0,
                "completeness": 1.0,
                "overall": 1.0,
                "reasoning": "无回答",
                "evaluation_method": "keyword",
                "success": True
            }

        answer_lower = answer.lower()
        keywords_found = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
        coverage = keywords_found / len(expected_keywords) if expected_keywords else 0

        # Convert coverage to 10-point scale with one decimal
        overall = round(coverage * 10, 1)
        overall = max(1.0, min(10.0, overall))  # Ensure within 1-10 range

        return {
            "relevance": overall,
            "accuracy": overall,
            "completeness": overall,
            "overall": overall,
            "reasoning": f"关键词覆盖率: {coverage*100:.1f}%",
            "evaluation_method": "keyword",
            "success": True
        }


class EvaluationResult:
    """Single evaluation result"""
    def __init__(self, question_id: int, question: str, answer: str, score: float,
                 details: Optional[Dict] = None, error: Optional[str] = None):
        self.question_id = question_id
        self.question = question
        self.answer = answer
        self.score = score
        self.details = details or {}
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question_id": self.question_id,
            "question": self.question,
            "answer": self.answer,
            "score": self.score,
            **self.details,
            "error": self.error
        }


def load_questions(questions_file: Path) -> List[Dict[str, Any]]:
    """Load questions from JSON file"""
    with open(questions_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("questions", [])


def run_evaluation(
    questions: List[Dict[str, Any]],
    rag_pipeline_fn,
    evaluator: LLMEvaluator,
    progress_callback=None
) -> Dict[str, Any]:
    """
    Run evaluation on a list of questions

    Args:
        questions: List of question dicts with id, question, expected_keywords
        rag_pipeline_fn: Function that takes a question and returns RAG answer
        evaluator: LLMEvaluator instance
        progress_callback: Optional callback(current, total) for progress updates

    Returns:
        Evaluation results summary
    """
    results = []
    total = len(questions)

    for i, q in enumerate(questions):
        try:
            # Get RAG answer
            rag_result = rag_pipeline_fn(q["question"])
            answer = rag_result.get("answer", "")

            # Evaluate
            eval_result = evaluator.evaluate(
                question=q["question"],
                answer=answer,
                expected_keywords=q.get("expected_keywords", [])
            )

            results.append(EvaluationResult(
                question_id=q["id"],
                question=q["question"],
                answer=answer,
                score=eval_result.get("overall", 0),
                details=eval_result
            ))

        except Exception as e:
            results.append(EvaluationResult(
                question_id=q["id"],
                question=q["question"],
                answer="",
                score=0,
                error=str(e)
            ))

        if progress_callback:
            progress_callback(i + 1, total)

    # Calculate summary
    successful = [r for r in results if not r.error]
    avg_score = sum(r.score for r in successful) / len(successful) if successful else 0

    return {
        "total_questions": total,
        "evaluated": len(results),
        "avg_score": avg_score,
        "results": [r.to_dict() for r in results]
    }
