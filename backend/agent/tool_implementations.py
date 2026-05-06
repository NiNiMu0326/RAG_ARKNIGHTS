"""
Tool implementations for AgenticRAG.
Each function takes a dict of arguments and returns a result.
"""

import json
import logging
import warnings
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


async def execute_rag_search(arguments: Dict[str, Any]) -> List[Dict]:
    """Execute arknights_rag_search tool.
    
    Internal pipeline: MultiChannelRetriever → SiliconFlowReranker → ParentDocumentRetriever
    
    Returns list of {content, source, score} dicts.
    """
    query = arguments.get("query", "")
    top_k = arguments.get("top_k", 5)

    if not query:
        return [{"error": "query parameter is required"}]

    try:
        from backend.rag.retrievers import MultiChannelRetriever
        from backend.lc.embeddings import SiliconFlowEmbeddings
        from backend.lc.reranker import SiliconFlowReranker
        from backend.rag.parent_document import ParentDocumentRetriever
        from backend import config

        # Load BM25 indexes (lazy, cached)
        bm25_indexes = _get_bm25_indexes()

        # Multi-channel retrieval
        embeddings = SiliconFlowEmbeddings(api_key=config.SILICONFLOW_API_KEY)
        retriever = MultiChannelRetriever(
            embeddings=embeddings,
            faiss_index_dir=config.FAISS_INDEX_DIR_STR,
            bm25_indexes=bm25_indexes,
            top_k_per_channel=8,
            final_top_k=top_k * 3,  # Get more for reranking
        )

        docs = retriever.invoke(query)

        # Rerank
        reranker = SiliconFlowReranker(api_key=config.SILICONFLOW_API_KEY, top_n=top_k)
        reranked_docs = reranker.compress_documents(docs, query)

        # Parent document expansion
        parent_retriever = ParentDocumentRetriever()
        results = []
        for doc in reranked_docs:
            chunk_id = doc.metadata.get("chunk_id", "")
            source = doc.metadata.get("source_collection", "")
            content = doc.page_content

            # Expand operators/stories chunks to full parent doc
            if chunk_id.startswith("operators_") or chunk_id.startswith("stories_"):
                chunk_data = {
                    "chunk_id": chunk_id,
                    "content": content,
                    "metadata": dict(doc.metadata),
                }
                src = "operators" if chunk_id.startswith("operators_") else "stories"
                expanded = parent_retriever.get_parent_content(chunk_data, src)
                if expanded and len(expanded) > len(content):
                    content = expanded

            results.append({
                "content": content[:2000],  # Truncate long content
                "source": source,
                "score": round(doc.metadata.get("relevance_score", 0.0), 4),
                "chunk_id": chunk_id,
            })

        # Deduplicate results after parent document expansion:
        # Multiple chunks from the same parent doc produce identical expanded content.
        # Keep the first occurrence (highest reranker score) for each unique content.
        seen_content = set()
        deduped = []
        for r in results:
            content_key = r["content"][:300]
            if content_key not in seen_content:
                seen_content.add(content_key)
                deduped.append(r)
        results = deduped

        return results

    except Exception as e:
        logger.error(f"RAG search failed: {e}", exc_info=True)
        return [{"error": f"检索失败: {str(e)}"}]


async def execute_graphrag_search(arguments: Dict[str, Any]) -> Dict:
    """Execute arknights_graphrag_search tool.
    
    Supports two modes:
    1. Single entity (entity): returns neighbors
    2. Two entities (entity1 + entity2): returns shortest path with edge info
    """
    entity = arguments.get("entity", "")
    entity1 = arguments.get("entity1", "")
    entity2 = arguments.get("entity2", "")

    try:
        from backend.rag.graphrag.query import get_graph_builder

        builder = get_graph_builder()
        if builder is None or builder.graph is None:
            return {"error": "知识图谱未加载，关系查询不可用"}

        if entity1 and entity2:
            # Two-entity path mode (max 3 hops to avoid meaningless long paths)
            result = builder.find_path(entity1, entity2, max_hops=3)
            if not result.get("path"):
                return {
                    "found": False,
                    "message": f"未找到 '{entity1}' 和 '{entity2}' 之间的直接关系路径（3跳以内）",
                    "entity1": entity1,
                    "entity2": entity2,
                }
            return {
                "found": True,
                "mode": "path",
                "entity1": entity1,
                "entity2": entity2,
                "path": result["path"],
                "edges": result["edges"],
            }
        elif entity:
            # Single-entity neighbor mode
            neighbors = builder.get_neighbors(entity)
            relations = builder.get_all_relations(entity)
            if not neighbors:
                return {
                    "found": False,
                    "message": f"未找到实体 '{entity}' 的关系信息",
                    "entity": entity,
                }
            return {
                "found": True,
                "mode": "neighbors",
                "entity": entity,
                "neighbors": neighbors,
                "relations": relations,
            }
        else:
            return {"error": "请提供 entity 或 entity1+entity2 参数"}

    except Exception as e:
        logger.error(f"GraphRAG search failed: {e}", exc_info=True)
        return {"error": f"关系查询失败: {str(e)}"}


async def execute_web_search(arguments: Dict[str, Any]) -> List[Dict]:
    """Execute web_search tool using Tavily + DuckDuckGo."""
    query = arguments.get("query", "")
    if not query:
        return [{"error": "query parameter is required"}]

    try:
        from backend.api.web_search import search as web_search

        results = web_search(query, limit=5)

        if not results:
            return [{"message": "未找到相关网络搜索结果", "query": query}]

        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": (r.get("snippet") or r.get("content", ""))[:500],
            }
            for r in results
        ]

    except Exception as e:
        logger.error(f"Web search failed: {e}", exc_info=True)
        return [{"error": f"网络搜索失败: {str(e)}"}]




# ===== Lazy-loaded singletons =====

_bm25_indexes = None
_bm25_lock = None


def _get_bm25_indexes():
    """Lazy-load BM25 indexes."""
    global _bm25_indexes, _bm25_lock
    import threading
    if _bm25_lock is None:
        _bm25_lock = threading.Lock()

    if _bm25_indexes is not None:
        return _bm25_indexes

    from backend.data.bm25_index import BM25Indexer
    from backend import config

    with _bm25_lock:
        if _bm25_indexes is not None:
            return _bm25_indexes

        indexes = {}
        for name in ["operators", "stories", "knowledge"]:
            try:
                path = config.get_bm25_index_path(name)
                indexes[name] = BM25Indexer.load(path)
                logger.info(f"Loaded BM25 index: {name}")
            except FileNotFoundError:
                logger.warning(f"BM25 index file not found for '{name}', collection will be unavailable. Run: python backend/data/bm25_index.py")
            except Exception as e:
                logger.error(f"Failed to load BM25 index for '{name}': {e}")

        _bm25_indexes = indexes
        return _bm25_indexes
