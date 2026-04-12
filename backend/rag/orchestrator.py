"""
RAGOrchestrator: wraps the LCEL chain with the same interface as backend/rag/orchestrator.py.
This ensures main.py requires zero changes beyond import path.
"""
import sys
import time
import warnings
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from langchain_core.documents import Document

from backend.rag.chain import build_rag_chain
from backend.data.bm25_index import BM25Indexer
from backend import config


@dataclass
class RAGAnswer:
    answer: str
    crag_level: str
    avg_score: float
    num_docs_used: int
    used_web_search: bool
    graph_results: Optional[Dict]
    retrieved_documents: Optional[List[Dict]] = None
    retrieved_doc_ids: List[str] = field(default_factory=list)  # 用于评估的文档ID列表
    pipeline_steps: List[Dict] = field(default_factory=list)
    total_time_ms: float = 0.0


_instance: Optional["RAGOrchestrator"] = None
_instance_lock = threading.Lock()


def get_orchestrator(api_key: str = None, faiss_index_dir: str = None, deepseek_api_key: str = None) -> "RAGOrchestrator":
    """Get or create singleton RAGOrchestrator instance (thread-safe)."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = RAGOrchestrator(api_key, faiss_index_dir, deepseek_api_key)
    return _instance


class RAGOrchestrator:
    def __init__(self, api_key: str = None, faiss_index_dir: str = None, deepseek_api_key: str = None):
        self.faiss_index_dir = faiss_index_dir or str(config.FAISS_INDEX_DIR)
        self._bm25_indexes: Dict[str, BM25Indexer] = {}
        self._bm25_loaded = False
        self._api_key = api_key or config.SILICONFLOW_API_KEY
        self._deepseek_api_key = deepseek_api_key or config.DEEPSEEK_API_KEY
        self._chain = None  # Lazy init after BM25 loaded

    def _load_bm25_indexes(self):
        if self._bm25_loaded:
            return
        self._bm25_loaded = True
        for name in ["operators", "stories", "knowledge"]:
            try:
                path = config.get_bm25_index_path(name)
                self._bm25_indexes[name] = BM25Indexer.load(path)
            except FileNotFoundError:
                warnings.warn(f"BM25 index not found for '{name}' collection.")
            except Exception as e:
                warnings.warn(f"Failed to load BM25 index for '{name}': {e}")

    def _get_chain(self):
        if self._chain is None:
            self._load_bm25_indexes()
            self._chain = build_rag_chain(
                siliconflow_api_key=self._api_key,
                deepseek_api_key=self._deepseek_api_key,
                faiss_index_dir=self.faiss_index_dir,
                bm25_indexes=self._bm25_indexes,
            )
        return self._chain

    def _docs_to_dicts(self, docs) -> List[Dict]:
        """Convert LangChain Document list to dict list for API response."""
        result = []
        for doc in docs:
            # Skip non-Document objects (e.g., strings or other invalid types)
            if not isinstance(doc, Document):
                continue
            # Skip docs with invalid content (e.g., internal state keys)
            content = doc.page_content
            if content in ("rewrite", "question", "history", "config", "recall_results",
                          "graph_results", "web_results", "answer", "crag"):
                continue
            result.append({
                "content": content,
                "relevance_score": doc.metadata.get("relevance_score", 0.0),
                "chunk_id": doc.metadata.get("chunk_id", ""),
                "source": doc.metadata.get("source_collection", ""),
                "metadata": {
                    "source_file": doc.metadata.get("source_file", ""),
                    **{k: v for k, v in doc.metadata.items()
                       if k not in ("chunk_id", "source_collection", "source_file")},
                },
            })
        return result

    def query(
        self,
        question: str,
        conversation_history: List[Dict] = None,
        use_parent_doc: bool = True,
        use_graphrag: bool = True,
        use_crag: bool = True,
        top_k_per_channel: int = 8,
        rerank_top_k: int = 5,
    ) -> RAGAnswer:
        """Execute the full RAG pipeline. Interface identical to backend/rag/orchestrator.py."""
        total_start = time.time()
        history = conversation_history or []

        chain_input = {
            "question": question,
            "history": history,
            "config": {
                "top_k_per_channel": top_k_per_channel,
                "rerank_top_k": rerank_top_k,
                "use_parent_doc": use_parent_doc,
                "use_graphrag": use_graphrag,
                "use_crag": use_crag,
            },
        }

        result = self._get_chain().invoke(chain_input)

        total_time = round((time.time() - total_start) * 1000)
        crag = result.get("crag")
        reranked_docs = result.get("reranked_docs", [])
        graph_results = result.get("graph_results")

        pipeline_steps = _build_pipeline_steps(result, total_time)

        # 判断是否为直接回答（聊天/闲聊），无检索过程
        is_direct = not result.get("rewrite", {}).get("needs_retrieval", True)
        if is_direct:
            crag_level = "DIRECT"
            avg_score = 1.0
        else:
            crag_level = crag.level if crag else "HIGH"
            avg_score = crag.avg_score if crag else 1.0

        return RAGAnswer(
            answer=result.get("answer", ""),
            crag_level=crag_level,
            avg_score=avg_score,
            num_docs_used=len(reranked_docs),
            used_web_search=crag.should_search_web if crag else False,
            graph_results=(
                graph_results
                if graph_results and graph_results.get("is_relation_query")
                else None
            ),
            retrieved_documents=self._docs_to_dicts(reranked_docs),
            retrieved_doc_ids=[doc.metadata.get("chunk_id", "") for doc in reranked_docs if isinstance(doc, Document)],
            pipeline_steps=pipeline_steps,
            total_time_ms=total_time,
        )

    def run_debug_step(
        self,
        step: int,
        question: str,
        conversation_history: List[Dict] = None,
        previous_results: Dict[int, Any] = None,
        use_parent_doc: bool = True,
        use_graphrag: bool = True,
        use_crag: bool = True,
        top_k_per_channel: int = 8,
        rerank_top_k: int = 5,
    ) -> Dict[str, Any]:
        """Run a specific RAG step. Interface identical to backend/rag/orchestrator.py."""
        history = conversation_history or []
        prev = previous_results or {}

        step_names = {
            1: ("Query Rewrite", "查询改写"),
            2: ("Multi-Channel Recall", "多通道召回"),
            3: ("Cross-Encoder Rerank", "交叉编码重排"),
            4: ("CRAG Judge", "CRAG 判断"),
            5: ("GraphRAG Query", "知识图谱查询"),
            6: ("Parent Document", "Parent文档扩展"),
            7: ("Web Search", "网络搜索"),
            8: ("Answer Generation", "答案生成"),
        }
        name, name_cn = step_names.get(step, ("Unknown", "未知"))
        step_start = time.time()

        try:
            step_result = self._run_single_step(
                step=step,
                question=question,
                history=history,
                prev=prev,
                cfg={
                    "top_k_per_channel": top_k_per_channel,
                    "rerank_top_k": rerank_top_k,
                    "use_parent_doc": use_parent_doc,
                    "use_graphrag": use_graphrag,
                    "use_crag": use_crag,
                },
            )
            return {
                "step": step,
                "name": name,
                "name_cn": name_cn,
                "input_data": step_result.get("input_data"),
                "output_data": step_result.get("output_data"),
                "time_ms": round((time.time() - step_start) * 1000),
                "can_continue": step < 8,
                "error": None,
            }
        except Exception as e:
            return {
                "step": step,
                "name": name,
                "name_cn": name_cn,
                "input_data": None,
                "output_data": {"error": str(e)},
                "time_ms": round((time.time() - step_start) * 1000),
                "can_continue": False,
                "error": str(e),
            }

    def _run_single_step(
        self, step: int, question: str, history: List, prev: Dict, cfg: Dict
    ) -> Dict:
        """Execute a single pipeline step using the component directly."""
        from backend.rag.query_rewriter import QueryRewriter
        from backend.rag.crag import CRAGJudge, CRAGStrategy
        from backend.rag.parent_document import ParentDocumentRetriever
        from backend.rag.graphrag.query import GraphRAGQuery
        from backend.lc.reranker import SiliconFlowReranker
        from backend.lc.embeddings import SiliconFlowEmbeddings

        if step == 1:
            rewriter = QueryRewriter(api_key=self._api_key)
            output = rewriter.rewrite(question, history)
            return {"input_data": {"question": question, "history": history},
                    "output_data": output}

        elif step == 2:
            sub_queries = prev.get(1, {}).get("queries", [question]) if isinstance(prev.get(1), dict) else [question]
            self._load_bm25_indexes()
            from backend.rag.retrievers import MultiChannelRetriever
            retriever = MultiChannelRetriever(
                embeddings=SiliconFlowEmbeddings(api_key=self._api_key),
                faiss_index_dir=self.faiss_index_dir,
                bm25_indexes=self._bm25_indexes,
                top_k_per_channel=cfg.get("top_k_per_channel", 8),
            )
            docs = retriever.invoke(sub_queries[0] if sub_queries else question)
            output = [{"chunk_id": d.metadata.get("chunk_id", ""), "content": d.page_content} for d in docs]
            return {"input_data": {"query": sub_queries[0] if sub_queries else question},
                    "output_data": output}

        elif step == 3:
            recall_raw = prev.get(2, [])
            if not recall_raw:
                raise ValueError("Step 2 (recall) must be executed first")
            docs = [Document(page_content=r.get("content", ""),
                             metadata={"chunk_id": r.get("chunk_id", "")})
                    for r in recall_raw]
            reranker = SiliconFlowReranker(api_key=self._api_key,
                                           top_n=cfg.get("rerank_top_k", 5))
            reranked = reranker.compress_documents(docs, question)
            output = [{"chunk_id": d.metadata.get("chunk_id", ""),
                       "content": d.page_content,
                       "relevance_score": d.metadata.get("relevance_score", 0.0)}
                      for d in reranked]
            return {"input_data": {"query": question, "num_docs": len(docs)},
                    "output_data": output}

        elif step == 4:
            reranked_raw = prev.get(3, [])
            if not reranked_raw:
                raise ValueError("Step 3 (rerank) must be executed first")
            doc_dicts = [{"relevance_score": r.get("relevance_score", 0.0)} for r in reranked_raw]
            judge = CRAGJudge()
            if cfg.get("use_crag", True):
                strategy = judge.judge(doc_dicts)
            else:
                avg_score = sum(d["relevance_score"] for d in doc_dicts) / len(doc_dicts) if doc_dicts else 0.0
                strategy = CRAGStrategy(
                    level="HIGH", avg_score=avg_score, should_search_web=False,
                    should_use_docs=True, num_low_score_docs=0, web_search_count=0,
                    reasoning="CRAG disabled")
            output = {"level": strategy.level, "avg_score": strategy.avg_score,
                      "should_search_web": strategy.should_search_web,
                      "num_low_score_docs": strategy.num_low_score_docs,
                      "web_search_count": strategy.web_search_count}
            return {"input_data": {"num_docs": len(doc_dicts)}, "output_data": output}

        elif step == 5:
            rewrite = prev.get(1, {}) if isinstance(prev.get(1), dict) else {}
            gq = GraphRAGQuery()
            output = gq.query_with_flags(
                question=question,
                is_relation_query=rewrite.get("is_relation_query", False),
                detected_operators=rewrite.get("detected_operators", []),
            )
            return {"input_data": {"question": question},
                    "output_data": output or {"is_relation_query": False, "results": []}}

        elif step == 6:
            reranked_raw = prev.get(3, [])
            pr = ParentDocumentRetriever()
            expanded = []
            for r in reranked_raw:
                chunk_id = r.get("chunk_id", "")
                content = r.get("content", "")
                if chunk_id.startswith("operators_"):
                    content = pr.get_parent_content(r, "operators")
                elif chunk_id.startswith("stories_"):
                    content = pr.get_parent_content(r, "stories")
                expanded.append({**r, "content": content})
            return {"input_data": {"num_docs": len(reranked_raw)},
                    "output_data": {"expanded": True, "num_docs": len(expanded), "documents": expanded}}

        elif step == 7:
            crag_raw = prev.get(4, {})
            if not crag_raw.get("should_search_web", False):
                return {"input_data": {"query": question},
                        "output_data": {"skipped": True, "reason": "CRAG未触发网络搜索"}}
            from backend.api.siliconflow import SiliconFlowClient
            sf = SiliconFlowClient(api_key=self._api_key)
            results = sf.search(question)
            return {"input_data": {"query": question},
                    "output_data": {"num_results": len(results) if results else 0}}

        elif step == 8:
            from backend.rag.answer_generator import make_answer_chain
            parent_docs = prev.get(6, {})
            if isinstance(parent_docs, dict) and "documents" in parent_docs:
                reranked_raw = parent_docs["documents"]
            else:
                reranked_raw = prev.get(3, [])
            docs = [Document(page_content=r.get("content", ""),
                             metadata={"relevance_score": r.get("relevance_score", 0.0),
                                       "chunk_id": r.get("chunk_id", "")})
                    for r in reranked_raw]
            graph_results = prev.get(5) if isinstance(prev.get(5), dict) else None
            state = {
                "question": question, "history": history,
                "reranked_docs": docs,
                "web_results": None,
                "graph_results": graph_results,
                "crag": None,
                "config": cfg,
            }
            answer_chain = make_answer_chain(api_key=config.SILICONFLOW_API_KEY,
                                             rerank_top_k=cfg.get("rerank_top_k", 10))
            result = answer_chain.invoke(state)
            return {"input_data": {"question": question, "num_docs": len(docs)},
                    "output_data": {"answer": result.get("answer", "")}}

        return {"input_data": {}, "output_data": {}}


def _build_pipeline_steps(result: Dict, total_time_ms: int = 0) -> List[Dict]:
    """Build pipeline_steps list for frontend debug panel compatibility.

    Uses real timing data from _step_timings when available, falls back to
    weighted estimation otherwise.
    """
    steps = []
    timings = result.get("_step_timings", {})

    # Real timing key → step name mapping
    real_time_keys = {
        "query_rewrite": "Query Rewrite",
        "recall": "Multi-Channel Recall",
        "rerank": "Cross-Encoder Rerank",
        "crag": "CRAG Judge",
        "graphrag": "GraphRAG Query",
        "web_search": "Web Search",
        "parent_doc": "Parent Document",
        "answer_gen": "Answer Generation",
    }

    def get_real_ms(step_name: str) -> Optional[int]:
        for key, name in real_time_keys.items():
            if name == step_name and key in timings:
                return timings[key]
        return None

    def add(name, name_cn, description, input_data=None, output_data=None):
        real = get_real_ms(name)
        time_ms = real if real is not None else 0
        steps.append({
            "step": len(steps) + 1,
            "name": name,
            "name_cn": name_cn,
            "time_ms": time_ms,
            "description": description,
            "input_data": input_data,
            "output_data": output_data,
        })

    rewrite = result.get("rewrite", {})
    add("Query Rewrite", "查询改写",
        f"改写为 {len(rewrite.get('queries', []))} 个查询",
        output_data=rewrite)

    recall_docs = result.get("recall_results", [])
    add("Multi-Channel Recall", "多通道召回",
        f"召回 {len(recall_docs)} 个文档",
        output_data={"total_recalled": len(recall_docs)})

    graph = result.get("graph_results")
    add("GraphRAG Query", "知识图谱查询",
        f"找到 {len(graph.get('results', [])) if graph else 0} 条关系",
        output_data=graph)

    reranked = result.get("reranked_docs", [])
    add("Cross-Encoder Rerank", "交叉编码重排",
        f"重排后保留 {len(reranked)} 个文档",
        output_data={"reranked": [{"chunk_id": d.metadata.get("chunk_id", ""),
                                    "relevance_score": d.metadata.get("relevance_score", 0.0)}
                                   for d in reranked]})

    crag = result.get("crag")
    if crag:
        add("CRAG Judge", "CRAG 判断",
            f"等级: {crag.level}, 分数: {crag.avg_score:.3f}",
            output_data={"level": crag.level, "avg_score": crag.avg_score,
                         "should_search_web": crag.should_search_web})

    add("Parent Document", "Parent文档扩展", "扩展文档内容")

    web = result.get("web_results")
    add("Web Search", "网络搜索",
        f"获取 {len(web)} 条网络结果" if web else "跳过",
        output_data={"web_results_count": len(web) if web else 0})

    add("Answer Generation", "答案生成", "生成最终回答",
        output_data={"answer_length": len(result.get("answer", ""))})

    return steps
