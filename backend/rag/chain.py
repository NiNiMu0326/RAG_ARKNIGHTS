"""
LCEL RAG chain assembly.
Composes all steps into a single Runnable chain with LangSmith tracing.
"""
import sys
import time
import warnings
import logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

from langchain_core.runnables import (
    RunnableLambda,
    RunnableParallel,
    RunnablePassthrough,
    RunnableBranch,
)
from langchain_core.documents import Document

from backend.rag.query_rewriter import make_query_rewrite_runnable
from backend.rag.crag import make_crag_runnable, CRAGStrategy
from backend.rag.answer_generator import make_answer_chain
from backend.rag.parent_document import ParentDocumentRetriever
from backend.rag.graphrag.query import GraphRAGQuery
from backend.lc.embeddings import SiliconFlowEmbeddings
from backend.lc.reranker import SiliconFlowReranker
from backend.rag.retrievers import MultiChannelRetriever
from backend.data.bm25_index import BM25Indexer
from backend import config

logger = logging.getLogger(__name__)


def _build_recall_fn(retriever: MultiChannelRetriever):
    """Return a function that performs multi-channel recall from state dict."""
    def _recall(state: Dict) -> List[Document]:
        t0 = time.time()
        rewrite = state.get("rewrite", {})
        queries = rewrite.get("queries", [state["question"]])
        cfg = state.get("config", {})

        retriever.top_k_per_channel = cfg.get("top_k_per_channel", 8)
        retriever.final_top_k = retriever.top_k_per_channel * 3

        if len(queries) == 1:
            docs = retriever.invoke(queries[0])
        else:
            all_docs: List[Document] = []
            seen_ids = set()
            with ThreadPoolExecutor(max_workers=len(queries)) as ex:
                futures = [ex.submit(retriever.invoke, q) for q in queries]
                for f in futures:
                    for doc in f.result():
                        cid = doc.metadata.get("chunk_id", doc.page_content[:40])
                        if cid not in seen_ids:
                            seen_ids.add(cid)
                            all_docs.append(doc)
            docs = all_docs

        elapsed = round((time.time() - t0) * 1000)
        logger.info(f"[Recall] {elapsed}ms, {len(docs)} docs for query: {queries}")
        # Store timing in a dict that flows through state
        timings = state.get("_step_timings", {})
        timings["recall"] = elapsed
        state["_step_timings"] = timings
        return docs
    return _recall


def _build_graphrag_fn(graphrag_query: GraphRAGQuery):
    """Return a function that runs GraphRAG from state dict."""
    def _graphrag(state: Dict) -> Dict:
        t0 = time.time()
        if not state.get("config", {}).get("use_graphrag", True):
            return {"is_relation_query": False, "results": []}
        rewrite = state.get("rewrite", {})
        is_relation = rewrite.get("is_relation_query", False)
        detected = rewrite.get("detected_operators", [])
        if not is_relation:
            return {"is_relation_query": False, "results": []}
        result = graphrag_query.query_with_flags(
            question=state["question"],
            is_relation_query=True,
            detected_operators=detected,
        )
        elapsed = round((time.time() - t0) * 1000)
        logger.info(f"[GraphRAG] {elapsed}ms")
        timings = state.get("_step_timings", {})
        timings["graphrag"] = elapsed
        # Return result as-is; timing is stored in state via _merge_parallel
        result["_step_timings"] = timings
        return result
    return _graphrag


def _build_rerank_fn(reranker: SiliconFlowReranker):
    """Return a function that reranks documents from state dict."""
    def _rerank(state: Dict) -> Dict:
        t0 = time.time()
        docs = state.get("recall_results", [])
        question = state["question"]
        rewrite = state.get("rewrite", {})
        queries = rewrite.get("queries", [question])
        cfg = state.get("config", {})
        rerank_top_k = cfg.get("rerank_top_k", 5)
        reranker.top_n = rerank_top_k

        # 如果没有召回文档，返回带空 reranked_docs 的完整 state
        if not docs:
            return {**state, "reranked_docs": []}

        # 确保 docs 是 Document 对象列表
        processed_docs = []
        for doc in docs:
            if isinstance(doc, Document):
                processed_docs.append(doc)
            elif isinstance(doc, str):
                processed_docs.append(Document(page_content=doc, metadata={}))
            elif isinstance(doc, dict):
                processed_docs.append(Document(
                    page_content=doc.get("content", ""),
                    metadata=doc.get("metadata", {})
                ))
            else:
                try:
                    processed_docs.append(Document(page_content=str(doc), metadata={}))
                except:
                    pass
        docs = processed_docs

        if not docs:
            return {**state, "reranked_docs": []}

        # Rerank with all sub-queries and merge results
        all_reranked: List[Document] = []
        seen_indices: set = set()

        for q in queries:
            reranked = reranker.compress_documents(docs, q)
            for doc in reranked:
                orig_idx = doc.metadata.get("original_index", -1)
                if orig_idx == -1:
                    key = doc.page_content[:80]
                else:
                    key = str(orig_idx)

                if key not in seen_indices:
                    seen_indices.add(key)
                    all_reranked.append(doc)

        all_reranked.sort(
            key=lambda d: d.metadata.get("relevance_score", 0.0), reverse=True
        )

        for i, doc in enumerate(all_reranked):
            if "original_index" not in doc.metadata:
                doc.metadata["original_index"] = i

        elapsed = round((time.time() - t0) * 1000)
        logger.info(f"[Rerank] {elapsed}ms, {len(all_reranked[:rerank_top_k])} docs after rerank")
        timings = state.get("_step_timings", {})
        timings["rerank"] = elapsed
        return {**state, "reranked_docs": all_reranked[:rerank_top_k], "_step_timings": timings}
    return _rerank


def _build_parent_doc_fn(parent_retriever: ParentDocumentRetriever):
    """Return a function that expands docs with parent content."""
    def _parent_doc(state: Dict) -> Dict:
        t0 = time.time()
        if not state.get("config", {}).get("use_parent_doc", True):
            return state
        docs = state.get("reranked_docs", [])
        expanded = []
        for doc in docs:
            # 处理 Document、dict 或 str 输入
            if isinstance(doc, str):
                expanded.append(Document(page_content=doc, metadata={}))
                continue
            elif isinstance(doc, dict):
                chunk_id = doc.get("chunk_id", "")
                content = doc.get("content", "")
                metadata = dict(doc.get("metadata", {}))
                # 保留 relevance_score
                if "relevance_score" in doc:
                    metadata["relevance_score"] = doc["relevance_score"]
            else:
                chunk_id = doc.metadata.get("chunk_id", "") if doc.metadata else ""
                content = doc.page_content
                metadata = dict(doc.metadata) if doc.metadata else {}

            if chunk_id.startswith("operators_"):
                content = parent_retriever.get_parent_content(
                    {"chunk_id": chunk_id, "content": content,
                     "metadata": metadata}, "operators"
                )
            elif chunk_id.startswith("stories_"):
                content = parent_retriever.get_parent_content(
                    {"chunk_id": chunk_id, "content": content,
                     "metadata": metadata}, "stories"
                )
            # 其他类型的 chunk 不扩展
            expanded.append(Document(page_content=content, metadata=metadata))
        elapsed = round((time.time() - t0) * 1000)
        logger.info(f"[ParentDoc] {elapsed}ms, expanded {len(expanded)} docs")
        timings = state.get("_step_timings", {})
        timings["parent_doc"] = elapsed
        # 保留所有 state 字段
        return {
            "reranked_docs": expanded,
            "question": state.get("question", ""),
            "history": state.get("history", []),
            "config": state.get("config", {}),
            "rewrite": state.get("rewrite", {}),
            "recall_results": state.get("recall_results", []),
            "graph_results": state.get("graph_results"),
            "web_results": state.get("web_results"),
            "crag": state.get("crag"),
            "_step_timings": timings,
        }
    return _parent_doc


def _build_web_search_fn(siliconflow_client):
    """Return a function that performs web search if CRAG LOW."""
    def _web_search(state: Dict) -> Dict:
        t0 = time.time()
        crag: Optional[CRAGStrategy] = state.get("crag")
        if not crag or not crag.should_search_web:
            logger.info(f"[WebSearch] SKIPPED (CRAG level={crag.level if crag else 'N/A'})")
            timings = state.get("_step_timings", {})
            timings["web_search"] = 0
            return {
                "web_results": None,
                "question": state.get("question", ""),
                "history": state.get("history", []),
                "config": state.get("config", {}),
                "rewrite": state.get("rewrite", {}),
                "recall_results": state.get("recall_results", []),
                "graph_results": state.get("graph_results"),
                "reranked_docs": state.get("reranked_docs", []),
                "crag": state.get("crag"),
                "_step_timings": timings,
            }
        question = state["question"]
        try:
            search_count = min(crag.web_search_count, 3)
            if search_count == 0:
                timings = state.get("_step_timings", {})
                timings["web_search"] = 0
                return {
                    "web_results": None,
                    "question": question,
                    "history": state.get("history", []),
                    "config": state.get("config", {}),
                    "rewrite": state.get("rewrite", {}),
                    "recall_results": state.get("recall_results", []),
                    "graph_results": state.get("graph_results"),
                    "reranked_docs": state.get("reranked_docs", []),
                    "crag": state.get("crag"),
                    "_step_timings": timings,
                }
            raw = siliconflow_client.search(question, limit=search_count)
            elapsed = round((time.time() - t0) * 1000)
            logger.info(f"[WebSearch] {elapsed}ms, got {len(raw) if raw else 0} results")
            timings = state.get("_step_timings", {})
            timings["web_search"] = elapsed

            if not raw:
                return {
                    "web_results": None,
                    "question": question,
                    "history": state.get("history", []),
                    "config": state.get("config", {}),
                    "rewrite": state.get("rewrite", {}),
                    "recall_results": state.get("recall_results", []),
                    "graph_results": state.get("graph_results"),
                    "reranked_docs": state.get("reranked_docs", []),
                    "crag": state.get("crag"),
                    "_step_timings": timings,
                }

            web_results = [
                {"title": r.get("title", ""), "url": r.get("url", ""),
                 "snippet": r.get("snippet", ""), "source": "web_search"}
                for r in raw[:search_count]
            ]

            # 用网络结果替换低分文档（与 backend_old 逻辑一致）
            doc_threshold = config.CRAG_LOW_THRESHOLD
            reranked_docs = list(state.get("reranked_docs", []))
            replaced_count = 0
            for i, doc in enumerate(reranked_docs):
                score = doc.metadata.get("relevance_score", 1.0) if isinstance(doc, Document) else doc.get("relevance_score", 1.0)
                if score < doc_threshold and replaced_count < len(web_results):
                    web = web_results[replaced_count]
                    reranked_docs[i] = Document(
                        page_content=f"[网络来源] {web['title']}\n{web['snippet']}",
                        metadata={
                            "source_file": web["title"],
                            "url": web["url"],
                            "relevance_score": 0.5,
                            "source": "web_search",
                        },
                    )
                    replaced_count += 1
            logger.info(f"[WebSearch] replaced {replaced_count} low-score docs with web results")

            # 保留所有 state 字段
            return {
                "web_results": web_results,
                "reranked_docs": reranked_docs,
                "question": question,
                "history": state.get("history", []),
                "config": state.get("config", {}),
                "rewrite": state.get("rewrite", {}),
                "recall_results": state.get("recall_results", []),
                "graph_results": state.get("graph_results"),
                "crag": state.get("crag"),
                "_step_timings": timings,
            }
        except Exception as e:
            elapsed = round((time.time() - t0) * 1000)
            logger.warning(f"[WebSearch] FAILED after {elapsed}ms: {e}")
            timings = state.get("_step_timings", {})
            timings["web_search"] = elapsed
            return {
                "web_results": None,
                "question": state.get("question", ""),
                "history": state.get("history", []),
                "config": state.get("config", {}),
                "rewrite": state.get("rewrite", {}),
                "recall_results": state.get("recall_results", []),
                "graph_results": state.get("graph_results"),
                "reranked_docs": state.get("reranked_docs", []),
                "crag": state.get("crag"),
                "_step_timings": timings,
            }
    return _web_search


def _merge_parallel(state: Dict) -> Dict:
    """合并并行结果 - 处理 RunnableParallel 的输出格式。
    
    RunnableParallel 输出: {"state": input, "recall_results": [...], "graph_results": {...}}
    """
    # 获取原始输入状态
    inner = dict(state.get("state", {}))
    
    # 获取 recall_results (现在是直接的列表)
    recall_result = state.get("recall_results", [])
    if isinstance(recall_result, list):
        inner["recall_results"] = recall_result
    elif isinstance(recall_result, dict) and "recall_results" in recall_result:
        # 处理嵌套的 {"recall_results": [...]} 格式
        inner["recall_results"] = recall_result["recall_results"]
    else:
        inner["recall_results"] = []
    
    # 获取 graph_results (现在是直接的对象)
    graph_result = state.get("graph_results")
    if isinstance(graph_result, dict):
        # 提取 graphrag 计时
        if "_step_timings" in graph_result:
            inner_timings = inner.get("_step_timings", {})
            inner_timings.update(graph_result.pop("_step_timings"))
            inner["_step_timings"] = inner_timings
        if "graph_results" in graph_result:
            inner["graph_results"] = graph_result["graph_results"]
        else:
            inner["graph_results"] = graph_result
    else:
        inner["graph_results"] = None
    
    return inner


def build_rag_chain(
    siliconflow_api_key: str = None,
    deepseek_api_key: str = None,
    faiss_index_dir: str = None,
    bm25_indexes: Dict = None,
) -> Any:
    """Build and return the full LCEL RAG chain.

    The chain accepts:
      {"question": str, "history": list, "config": dict}

    The chain returns the state dict with "answer" key added.
    """
    sf_key = siliconflow_api_key or config.SILICONFLOW_API_KEY
    ds_key = deepseek_api_key or config.DEEPSEEK_API_KEY
    index_dir = faiss_index_dir or config.FAISS_INDEX_DIR_STR
    bm25 = bm25_indexes or {}

    embeddings = SiliconFlowEmbeddings(api_key=sf_key)
    retriever = MultiChannelRetriever(
        embeddings=embeddings,
        faiss_index_dir=index_dir,
        bm25_indexes=bm25,
    )
    reranker = SiliconFlowReranker(api_key=sf_key)
    parent_retriever = ParentDocumentRetriever()
    graphrag_query = GraphRAGQuery()

    from backend.api.siliconflow import SiliconFlowClient
    sf_client = SiliconFlowClient(api_key=sf_key)

    # Build runnables
    query_rewrite = make_query_rewrite_runnable(api_key=sf_key)
    recall_runnable = RunnableLambda(_build_recall_fn(retriever), name="MultiChannelRecall")
    graphrag_runnable = RunnableLambda(_build_graphrag_fn(graphrag_query), name="GraphRAGQuery")
    rerank_runnable = RunnableLambda(_build_rerank_fn(reranker), name="CrossEncoderRerank")
    crag_runnable = make_crag_runnable(use_crag=True)
    parent_doc_runnable = RunnableLambda(_build_parent_doc_fn(parent_retriever), name="ParentDocument")
    web_search_runnable = RunnableLambda(_build_web_search_fn(sf_client), name="WebSearch")
    answer_runnable = make_answer_chain(api_key=sf_key)

    def _is_direct_answer(state: Dict) -> bool:
        return not state.get("rewrite", {}).get("needs_retrieval", True)

    def _direct_answer(state: Dict) -> Dict:
        return {**state, "answer": state["rewrite"].get("answer", "")}

    parallel_recall_graph = RunnableParallel({
        "state": RunnablePassthrough(),
        "recall_results": recall_runnable,
        "graph_results": graphrag_runnable,
    })

    full_pipeline = (
        parallel_recall_graph
        | RunnableLambda(_merge_parallel, name="MergeParallel")
        | rerank_runnable
        | crag_runnable
        | parent_doc_runnable
        | web_search_runnable
        | answer_runnable
    )

    chain = (
        query_rewrite
        | RunnableBranch(
            (_is_direct_answer, RunnableLambda(_direct_answer, name="DirectAnswer")),
            full_pipeline,
        )
    ).with_config(run_name="ArknightsRAGPipeline")

    return chain
