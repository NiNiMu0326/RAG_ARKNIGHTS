"""
Answer generation chain using LangChain LCEL:
  ChatPromptTemplate | SiliconFlowChatModel | StrOutputParser
"""
import sys
import time
import logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Dict, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_core.documents import Document

from backend.lc.llm import SiliconFlowChatModel
from backend import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "你是一个明日方舟游戏知识问答助手。请基于提供的文档回答问题，保持准确和简洁。"

USER_PROMPT_TEMPLATE = """你是一个明日方舟游戏知识问答助手。请根据以下参考资料回答用户问题。

## 对话历史
{history}

## 用户问题
{question}

## 【参考文档】（来源：本地检索，高相关性）
{documents}

## 回答要求
1. 基于参考文档内容回答，不要编造信息
2. 如果参考文档与网络搜索补充内容冲突，以参考文档为准
3. 引用相关文档时使用 [1] [2] 等标记
4. 回答应该准确、完整、简洁
5. 直接回答，不要进行深度思考或长篇推理分析

## 【网络搜索补充】（来源：网络搜索，仅作参考）
{web_results}

{graph_section}
## 回答
"""


def _build_docs_text(documents, max_docs: int = 10) -> str:
    docs = documents[:max_docs]
    parts = []
    for i, doc in enumerate(docs, 1):
        # 处理 Document、dict 或 str 输入
        if isinstance(doc, Document):
            source = doc.metadata.get("source_file", doc.metadata.get("chunk_id", f"Doc {i}"))
            score = doc.metadata.get("relevance_score", 0.0)
            content = doc.page_content
        elif isinstance(doc, dict):
            source = doc.get("metadata", {}).get("source_file", doc.get("chunk_id", f"Doc {i}"))
            score = doc.get("relevance_score", 0.0)
            content = doc.get("content", "")
        elif isinstance(doc, str):
            source = f"Doc {i}"
            score = 0.0
            content = doc
        else:
            continue

        score_text = f" (相关度: {score:.2f})" if score > 0 else ""
        parts.append(f"[{i}] {source}{score_text}:\n{content}")
    return "\n\n".join(parts) if parts else "无相关文档"


def _build_web_text(web_results: Optional[List[Dict]]) -> str:
    if not web_results:
        return "无"
    parts = []
    for i, r in enumerate(web_results, 1):
        title = r.get("title", "Result")
        snippet = r.get("snippet", "")
        parts.append(f"[{i}] {title}:\n{snippet}")
    return "\n".join(parts)


def _build_graph_section(graph_results: Optional[Dict]) -> str:
    if not graph_results or not graph_results.get("is_relation_query"):
        return ""
    results = graph_results.get("results", [])
    if not results:
        return ""
    operators = graph_results.get("detected_operators", [])
    lines = ["## 知识图谱关系"]
    direct = [r for r in results if r.get("operator1") in operators and r.get("operator2") in operators]
    others: Dict[str, List] = {}
    for r in results:
        if r not in direct:
            op1 = r.get("operator1", "")
            others.setdefault(op1, []).append(r)
    if direct:
        lines.append("【直接关系】")
        for r in direct:
            lines.append(f"- {r['operator1']} 与 {r['operator2']} 是{r['relation']}：{r['description']}")
    if others:
        lines.append("\n【各自关系】")
        for op, rels in others.items():
            lines.append(f"\n{op} 的关系：")
            for r in rels:
                desc = r.get('description', '')
                if desc:
                    lines.append(f"  - {r['operator2']}：{r['relation']}（{desc}）")
                else:
                    lines.append(f"  - {r['operator2']}：{r['relation']}")
    return "\n".join(lines) + "\n"


def _build_history_text(history: Optional[List[Dict]]) -> str:
    if not history:
        return "无"
    return "\n".join(f"{m['role']}: {m['content']}" for m in history[-5:])


def make_answer_chain(api_key: str = None, rerank_top_k: int = 10):
    """Build the LCEL answer generation chain.

    Input state: {..., "reranked_docs": List[Document], "web_results": ...,
                       "graph_results": ..., "question": str, "history": list,
                       "crag": CRAGStrategy}
    Output state: same + {"answer": str}
    """
    final_api_key = api_key or config.SILICONFLOW_API_KEY

    llm = SiliconFlowChatModel(
        api_key=final_api_key,
        model="Pro/Qwen/Qwen2.5-7B-Instruct",
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", USER_PROMPT_TEMPLATE),
    ])

    answer_chain_inner = prompt | llm | StrOutputParser()

    def _generate(state: Dict) -> Dict:
        t0 = time.time()
        docs = state.get("reranked_docs", [])[:rerank_top_k]
        question = state["question"]
        history = state.get("history", [])
        web_results = state.get("web_results")
        graph_results = state.get("graph_results")

        answer = answer_chain_inner.invoke({
            "history": _build_history_text(history),
            "question": question,
            "documents": _build_docs_text(docs, max_docs=rerank_top_k),
            "web_results": _build_web_text(web_results),
            "graph_section": _build_graph_section(graph_results),
        })
        elapsed = round((time.time() - t0) * 1000)
        logger.info(f"[AnswerGen] {elapsed}ms")
        timings = state.get("_step_timings", {})
        timings["answer_gen"] = elapsed
        # 保留 reranked_docs 到返回状态，供前端使用
        return {**state, "answer": answer.strip(), "reranked_docs": docs, "_step_timings": timings}

    return RunnableLambda(_generate, name="AnswerGeneration")
