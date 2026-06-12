"""
RAG 检索质量评估脚本
使用 RAGAS 框架评估 arknights_rag_search 工具的检索效果

评估指标 (RAGAS 0.4.x, 使用旧版 ragas.metrics 接口兼容 evaluate()):
- ContextRelevance:      检索结果与问题的相关性 (只需 question + contexts)
- LLMContextRecall:      检索结果对 ground_truth 的覆盖度 (需要 reference)

用法:
    python backend/evaluation/rag_eval.py                       # LLM评估模式 (推荐)
    python backend/evaluation/rag_eval.py --no-llm              # NonLLM模式 (字符串匹配)
    python backend/evaluation/rag_eval.py --top-k 10            # 设置检索返回数量
    python backend/evaluation/rag_eval.py --output-dir results  # 设置输出目录
"""

import asyncio
import json
import sys
import os
import argparse
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from backend import config

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import nest_asyncio
nest_asyncio.apply()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def retrieve_contexts(question: str, top_k: int = 5) -> List[str]:
    """调用 RAG 检索获取上下文文本列表。"""
    from backend.agent.tool_implementations import execute_rag_search

    result = await execute_rag_search({"query": question, "top_k": top_k})

    contexts = []
    for item in result:
        if isinstance(item, dict) and "content" in item and "error" not in item:
            contexts.append(item["content"])
    return contexts


def run_evaluation_no_llm(dataset):
    """使用 NonLLM 指标评估 (基于字符串匹配, 无需 LLM API)。"""
    from ragas import evaluate
    from ragas.metrics.collections import (
        NonLLMContextPrecisionWithReference,
        NonLLMContextRecall,
    )

    metrics = [
        NonLLMContextPrecisionWithReference(),
        NonLLMContextRecall(),
    ]

    logger.info("使用 NonLLM 指标评估 (无需 LLM API)...")
    result = evaluate(dataset=dataset, metrics=metrics)
    return result


def run_evaluation_with_llm(dataset):
    """使用 LLM 指标评估 (通过 DeepSeek-V4-Flash)。

    指标:
    - ContextRelevance: 检索结果与问题的相关性 (dual-judge, 只需 question + contexts)
    - LLMContextRecall: 检索结果对 ground_truth 的覆盖度 (需要 reference)
    """
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    from ragas import evaluate
    from ragas.metrics import (
        ContextRelevance,
        LLMContextRecall,
    )
    from ragas.llms import LangchainLLMWrapper
    from langchain_openai import ChatOpenAI

    # 使用 DeepSeek 模型作为评判 LLM
    judge_llm = ChatOpenAI(
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com/v1",
        api_key=config.DEEPSEEK_API_KEY,
        temperature=0,
        timeout=60,
        max_tokens=8192,
    )
    wrapped_llm = LangchainLLMWrapper(judge_llm)

    metrics = [
        ContextRelevance(llm=wrapped_llm),
        LLMContextRecall(llm=wrapped_llm),
    ]

    logger.info("使用 LLM 指标评估 (DeepSeek-V4-Flash 作为 judge)...")
    logger.info("  - ContextRelevance: 检索结果与问题的相关性")
    logger.info("  - LLMContextRecall: 检索结果对 ground_truth 的覆盖度")

    result = evaluate(dataset=dataset, metrics=metrics)
    return result


async def build_dataset(test_cases: List[Dict], top_k: int = 5, use_reference_contexts: bool = False):
    """构建 RAGAS 评估数据集。

    RAGAS 0.4.x 旧版接口使用以下列名:
    - user_input: 问题
    - retrieved_contexts: 检索到的上下文
    - reference: 标准答案 (ground_truth)
    - reference_contexts: 标准上下文 (NonLLM 模式使用)
    """
    from datasets import Dataset

    questions = []
    contexts_list = []
    references = []
    reference_contexts_list = []
    categories = []
    skipped = 0

    for i, tc in enumerate(test_cases):
        q = tc["question"]
        gt = tc["ground_truth"]
        cat = tc.get("category", "unknown")

        logger.info(f"[{i+1}/{len(test_cases)}] 检索: {q}")
        t0 = time.time()
        contexts = await retrieve_contexts(q, top_k=top_k)
        elapsed = time.time() - t0
        logger.info(f"  -> 返回 {len(contexts)} 个结果 ({elapsed:.1f}s)")

        if not contexts:
            logger.warning("  -> 跳过: 无检索结果")
            skipped += 1
            continue

        questions.append(q)
        contexts_list.append(contexts)
        references.append(gt)
        categories.append(cat)

        if use_reference_contexts:
            reference_contexts_list.append([gt])

    if not questions:
        logger.error("所有测试用例均无检索结果, 无法评估")
        return None

    # RAGAS 0.4.x 旧版接口列名
    data_dict = {
        "user_input": questions,
        "retrieved_contexts": contexts_list,
        "reference": references,
        "category": categories,
    }
    if use_reference_contexts:
        data_dict["reference_contexts"] = reference_contexts_list

    dataset = Dataset.from_dict(data_dict)

    logger.info(f"数据集构建完成: {len(questions)} 条 (跳过 {skipped} 条)")
    return dataset


def print_results(result_df, metrics_names):
    """打印评估结果。"""
    print()
    print("=" * 60)
    print("  RAG 检索质量评估报告")
    print("=" * 60)

    # 总体得分
    print()
    print("总体指标:")
    print("-" * 40)
    for col in result_df.columns:
        if col in metrics_names:
            mean_val = result_df[col].mean()
            min_val = result_df[col].min()
            max_val = result_df[col].max()
            print(f"  {col:30s}  mean={mean_val:.3f}  min={min_val:.3f}  max={max_val:.3f}")

    # 逐题得分
    print()
    print("逐题详情:")
    print("-" * 40)
    for i, row in result_df.iterrows():
        q = row.get("user_input", f"Q{i+1}")
        q_short = q[:40] + "..." if len(q) > 40 else q
        print(f"  [{i+1}] {q_short}")
        for col in result_df.columns:
            if col in metrics_names:
                val = row[col]
                if val is not None and str(val) != "nan":
                    print(f"      {col}: {val:.3f}")
        print()

    # 按类别汇总
    if "category" in result_df.columns:
        print("按类别汇总:")
        print("-" * 40)
        for cat in result_df["category"].unique():
            cat_df = result_df[result_df["category"] == cat]
            print(f"  [{cat}] ({len(cat_df)} items)")
            for col in result_df.columns:
                if col in metrics_names:
                    mean_val = cat_df[col].mean()
                    if str(mean_val) != "nan":
                        print(f"    {col}: {mean_val:.3f}")
            print()

    print("=" * 60)


def save_results(result_df, output_dir: str = "backend/evaluation/results"):
    """保存评估结果。"""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    csv_path = os.path.join(output_dir, f"rag_eval_{timestamp}.csv")
    json_path = os.path.join(output_dir, f"rag_eval_{timestamp}.json")

    result_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    result_df.to_json(json_path, orient="records", force_ascii=False, indent=2)

    logger.info(f"结果已保存: {csv_path}")
    logger.info(f"结果已保存: {json_path}")
    return csv_path, json_path


async def main():
    parser = argparse.ArgumentParser(description="RAG 检索质量评估")
    parser.add_argument("--test-file", default="backend/evaluation/test_cases.json",
                        help="测试用例 JSON 文件路径")
    parser.add_argument("--top-k", type=int, default=5, help="RAG 检索返回的结果数")
    parser.add_argument("--no-llm", action="store_true",
                        help="使用 NonLLM 指标 (更快但精度较低)")
    parser.add_argument("--output-dir", default="backend/evaluation/results",
                        help="结果输出目录")
    args = parser.parse_args()

    # 加载测试用例
    logger.info(f"加载测试用例: {args.test_file}")
    with open(args.test_file, "r", encoding="utf-8") as f:
        test_cases = json.load(f)
    logger.info(f"共 {len(test_cases)} 条测试用例")

    # 构建数据集
    dataset = await build_dataset(
        test_cases, top_k=args.top_k,
        use_reference_contexts=args.no_llm,
    )
    if dataset is None:
        sys.exit(1)

    # 选择评估模式
    if args.no_llm:
        result = run_evaluation_no_llm(dataset)
        metrics_names = [
            "non_llm_context_precision_with_reference",
            "non_llm_context_recall",
        ]
    else:
        result = run_evaluation_with_llm(dataset)
        metrics_names = [
            "nv_context_relevance",
            "context_recall",
        ]

    # 输出结果
    result_df = result.to_pandas()
    print_results(result_df, metrics_names)

    # 保存结果
    save_results(result_df, args.output_dir)


if __name__ == "__main__":
    asyncio.run(main())
