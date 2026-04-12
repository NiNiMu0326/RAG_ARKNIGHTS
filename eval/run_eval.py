"""
RAG 评估脚本
运行完整评估流程并生成报告

使用方法:
    python eval/run_eval.py
    python eval/run_eval.py --output report.json
    python eval/run_eval.py --questions eval/questions.json
"""
import sys
import json
import argparse
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.rag_eval import (
    run_evaluation,
    load_questions,
    generate_report,
    LLMEvaluator,
    calculate_recall_at_k,
    calculate_precision_at_k,
    calculate_f1_at_k,
    calculate_mrr,
    calculate_ndcg_at_k,
    calculate_rouge,
    calculate_keyword_coverage
)
from backend import config
from backend.rag.orchestrator import get_orchestrator


def rag_pipeline(question: str) -> dict:
    """
    RAG 管道函数，用于评估
    """
    try:
        orch = get_orchestrator(
            api_key=str(config.SILICONFLOW_API_KEY),
            deepseek_api_key=str(config.DEEPSEEK_API_KEY)
        )
        result = orch.query(
            question=question,
            use_parent_doc=True,
            use_graphrag=True,
            use_crag=True,
            rerank_top_k=5
        )
        return {
            "answer": result.answer,
            "retrieved_docs": result.retrieved_doc_ids
        }
    except Exception as e:
        print(f"  [ERROR] RAG pipeline failed: {e}")
        return {"answer": "", "retrieved_docs": []}


def main():
    parser = argparse.ArgumentParser(description="RAG 评估工具")
    parser.add_argument("--questions", "-q", default="eval/questions.json", help="问题文件路径")
    parser.add_argument("--output", "-o", default=None, help="输出报告路径 (JSON)")
    parser.add_argument("--no-llm", action="store_true", help="跳过 LLM 评估")
    parser.add_argument("--show-details", "-d", action="store_true", help="显示每个问题的详细评估")
    args = parser.parse_args()

    questions_file = Path(args.questions)
    if not questions_file.exists():
        print(f"[ERROR] 问题文件不存在: {questions_file}")
        return

    print("=" * 60)
    print("RAG 评估系统")
    print("=" * 60)
    
    # 加载问题
    print(f"\n[1/4] 加载问题: {questions_file}")
    questions = load_questions(questions_file)
    print(f"      共 {len(questions)} 个问题")
    
    # 创建评估器
    print("\n[2/4] 初始化评估器")
    if args.no_llm:
        evaluator = None
        print("      LLM 评估: 跳过")
    else:
        try:
            # 使用 SiliconFlow API + DeepSeek 模型进行评估
            evaluator = LLMEvaluator(str(config.SILICONFLOW_API_KEY))
            print(f"      LLM 评估: 已启用 (模型: {evaluator.eval_model})")
        except Exception as e:
            print(f"      LLM 评估: 失败 ({e})，将使用关键词评估")
            evaluator = None
    
    # 运行评估
    print("\n[3/4] 运行 RAG 评估...")
    print("-" * 40)
    
    def progress(current, total):
        print(f"\r      进度: {current}/{total}", end="", flush=True)
    
    evaluation_result = run_evaluation(
        questions=questions,
        rag_pipeline_fn=rag_pipeline,
        evaluator=evaluator,
        progress_callback=progress
    )
    
    print("\n" + "-" * 40)
    
    # 生成报告
    print("\n[4/4] 生成评估报告")
    report = generate_report(evaluation_result)
    
    # 打印汇总
    summary = evaluation_result.get("summary", {})
    print("\n" + "=" * 60)
    print("评估结果汇总")
    print("=" * 60)
    
    print(f"""
总问题数: {summary.get('total_questions', 0)}
成功评估: {summary.get('evaluated', 0)}
评估失败: {summary.get('failed', 0)}

【检索指标】(满分10分)
  召回率 @5:    {summary.get('retrieval', {}).get('avg_recall_5', 0):.2f}
  准确率 @5:    {summary.get('retrieval', {}).get('avg_precision_5', 0):.2f}
  F1 @5:       {summary.get('retrieval', {}).get('avg_f1_5', 0):.2f}
  MRR:         {summary.get('retrieval', {}).get('avg_mrr', 0):.2f}
  NDCG @5:     {summary.get('retrieval', {}).get('avg_ndcg_5', 0):.2f}

【生成指标】(满分10分)
  检索相关性:   {summary.get('generation', {}).get('avg_retrieval_relevance', 0):.2f}
  答案相关性:   {summary.get('generation', {}).get('avg_answer_relevance', 0):.2f}
  答案准确性:   {summary.get('generation', {}).get('avg_answer_accuracy', 0):.2f}

【综合评分】
  总分: {summary.get('overall', {}).get('avg_score', 0):.2f} / 10
""")
    
    # 显示详细结果
    if args.show_details:
        print("\n" + "=" * 60)
        print("详细结果")
        print("=" * 60)
        for r in evaluation_result.get("results", []):
            print(f"\n[问题 {r['question_id']}] {r['question']}")
            if r.get("error"):
                print(f"  [ERROR] {r['error']}")
                continue
            print(f"  综合分数: {r['overall_score']:.2f}/10")
            print(f"  检索: recall={r['recall_5']:.1f}, precision={r['precision_5']:.1f}, f1={r['f1_5']:.1f}")
            print(f"  生成: 相关={r['answer_relevance']:.1f}, 准确={r['answer_accuracy']:.1f}")
            if r.get("llm_reasoning"):
                print(f"  LLM评价: {r['llm_reasoning']}")
    
    # 保存报告
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(evaluation_result, f, ensure_ascii=False, indent=2)
        print(f"\n报告已保存: {output_path}")
    
    # 同时保存 Markdown 报告
    md_path = Path(args.output or "eval_report").with_suffix(".md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Markdown 报告: {md_path}")


if __name__ == "__main__":
    main()
