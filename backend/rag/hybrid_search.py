import sys
import time
import hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from typing import List, Dict, Tuple, Optional
import config
from backend.api.siliconflow import SiliconFlowClient
from backend.storage.chroma_client import ChromaClientWrapper
from backend.data.bm25_index import BM25Indexer
import chromadb.errors

RRF_K = config.RRF_K  # 60
VECTOR_WEIGHT = getattr(config, 'VECTOR_WEIGHT', 0.5)  # Default 0.5 for balanced search

# Cache for hybrid search results (query -> results)
# 5 hours TTL = 18000 seconds
_hybrid_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_HYBRID_CACHE_TTL = 18000
_HYBRID_CACHE_MAX_SIZE = 200

def _get_cache_key(query: str, collection_name: str, top_k: int, vector_weight: float = 0.5, inner_top_k: int = 20) -> str:
    """Generate cache key for hybrid search."""
    key_str = f"{query}:{collection_name}:{top_k}:{vector_weight}:{inner_top_k}"
    return hashlib.md5(key_str.encode('utf-8')).hexdigest()

def _get_cached_result(cache_key: str) -> Optional[List[Dict]]:
    """Get cached result if not expired."""
    if cache_key in _hybrid_cache:
        timestamp, results = _hybrid_cache[cache_key]
        if time.time() - timestamp < _HYBRID_CACHE_TTL:
            return results
        else:
            del _hybrid_cache[cache_key]
    return None

def _set_cached_result(cache_key: str, results: List[Dict]) -> None:
    """Set cached result with TTL."""
    if len(_hybrid_cache) >= _HYBRID_CACHE_MAX_SIZE:
        # Remove oldest entry
        oldest_key = next(iter(_hybrid_cache))
        del _hybrid_cache[oldest_key]
    _hybrid_cache[cache_key] = (time.time(), results)

def clear_hybrid_cache() -> None:
    """Clear hybrid search cache."""
    global _hybrid_cache
    _hybrid_cache.clear()

def rrf_fusion(rankings: List[Dict[str, int]], k: int = 60) -> Dict[str, float]:
    """Reciprocal Rank Fusion for combining multiple ranked lists.

    Args:
        rankings: List of dicts mapping doc_id to rank (1=best)
        k: RRF parameter (default 60)

    Returns:
        Dict mapping doc_id to RRF score
    """
    scores = {}
    for ranking in rankings:
        for doc_id, rank in ranking.items():
            if doc_id not in scores:
                scores[doc_id] = 0.0
            scores[doc_id] += 1.0 / (k + rank)
    return scores

def hybrid_search(
    query: str,
    collection_name: str,
    chroma_client: ChromaClientWrapper,
    bm25_indexer: BM25Indexer,
    vector_weight: float = None,
    top_k: int = 10,
    inner_top_k: int = 20
) -> List[Dict]:
    """Perform hybrid search on a single collection using vector + BM25 + RRF.

    Args:
        query: Search query
        collection_name: ChromaDB collection name
        chroma_client: ChromaDB client wrapper
        bm25_indexer: BM25 indexer
        vector_weight: Weight for vector search (0-1), None uses config default
        top_k: Final number of results to return
        inner_top_k: Number of results to fetch from each search method

    Returns:
        List of dicts with chunk_id, content, metadata, score, source
    """
    # Check cache first
    weight = vector_weight if vector_weight is not None else VECTOR_WEIGHT
    cache_key = _get_cache_key(query, collection_name, top_k, weight, inner_top_k)
    cached_results = _get_cached_result(cache_key)
    if cached_results is not None:
        return cached_results

    # 1. Vector search (inner_top_k)
    try:
        vector_results = chroma_client.search(collection_name, query, n_results=inner_top_k)
    except (chromadb.errors.ChromaError, ConnectionError) as e:
        import warnings
        warnings.warn(f"Vector search failed: {e}")
        vector_results = []

    # 2. BM25 search (inner_top_k)
    bm25_indices = bm25_indexer.retrieve(query, top_k=inner_top_k)
    bm25_results = []
    if bm25_indexer.corpus and hasattr(bm25_indexer, 'corpus_ids') and bm25_indexer.corpus_ids:
        # Create mapping from index to corpus_id
        for idx in bm25_indices:
            if idx is not None and idx < len(bm25_indexer.corpus):
                bm25_results.append({
                    'chunk_id': bm25_indexer.corpus_ids[idx],
                    'content': bm25_indexer.corpus[idx]
                })

    # 3. Build rankings for RRF
    # Vector ranking (1=best)
    vector_ranking = {r['chunk_id']: i+1 for i, r in enumerate(vector_results) if r.get('content')}
    # BM25 ranking (1=best)
    bm25_ranking = {r['chunk_id']: i+1 for i, r in enumerate(bm25_results) if r.get('content')}

    # 4. Standard RRF fusion with weighted combination
    # Compute RRF score for each method: score = 1 / (k + rank)
    all_doc_ids = set(vector_ranking.keys()) | set(bm25_ranking.keys())

    combined_scores = {}
    for doc_id in all_doc_ids:
        # RRF score for vector search
        vec_rrf = 1.0 / (RRF_K + vector_ranking.get(doc_id, RRF_K + 100))
        # RRF score for BM25 search
        bm25_rrf = 1.0 / (RRF_K + bm25_ranking.get(doc_id, RRF_K + 100))
        # Weighted combination of RRF scores
        combined_scores[doc_id] = weight * vec_rrf + (1 - weight) * bm25_rrf

    # Sort by combined score
    sorted_docs = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

    # 5. Build results with content
    results = []
    all_vector_results = {r['chunk_id']: r for r in vector_results}
    all_bm25_results = {r['chunk_id']: r for r in bm25_results}

    for doc_id, score in sorted_docs:
        content = ""
        metadata = {}
        distance = 0.0
        vector_score = 0.0
        bm25_score = 0.0

        if doc_id in all_vector_results:
            content = all_vector_results[doc_id].get('content', '')
            metadata = all_vector_results[doc_id].get('metadata', {})
            distance = all_vector_results[doc_id].get('distance', 0.0)
            vector_score = 1.0 / (RRF_K + vector_ranking.get(doc_id, RRF_K + 100))
        if doc_id in all_bm25_results:
            content = content or all_bm25_results[doc_id].get('content', '')
            bm25_score = 1.0 / (RRF_K + bm25_ranking.get(doc_id, RRF_K + 100))

        results.append({
            'chunk_id': doc_id,
            'content': content,
            'metadata': metadata,
            'score': score,
            'distance': distance,
            'vector_score': vector_score,
            'bm25_score': bm25_score,
            'source': collection_name
        })

    # Cache results before returning
    _set_cached_result(cache_key, results)

    return results