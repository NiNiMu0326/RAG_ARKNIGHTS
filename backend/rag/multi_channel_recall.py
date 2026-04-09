import sys
import time
import warnings
import hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from typing import List, Dict, Tuple, Optional
import config
from concurrent.futures import ThreadPoolExecutor, as_completed
from backend.api.siliconflow import SiliconFlowClient
from backend.storage.chroma_client import ChromaClientWrapper
from backend.data.bm25_index import BM25Indexer
from backend.rag.hybrid_search import hybrid_search

# Get vector weight from config, can be overridden via parameter
_VECTOR_WEIGHT = getattr(config, 'VECTOR_WEIGHT', 0.5)

# Cache for multi-channel recall results
_recall_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_RECALL_CACHE_TTL = 18000  # 5 hours
_RECALL_CACHE_MAX_SIZE = 200

def _get_recall_cache_key(query: str, top_k_per_channel: int, final_top_k: int, rrf_k: int, vector_weight: float = None) -> str:
    """Generate cache key for multi-channel recall."""
    vw = vector_weight if vector_weight is not None else _VECTOR_WEIGHT
    key_str = f"{query}:{top_k_per_channel}:{final_top_k}:{rrf_k}:{vw}"
    return hashlib.md5(key_str.encode('utf-8')).hexdigest()

def _get_cached_recall(cache_key: str) -> Optional[List[Dict]]:
    """Get cached recall result if not expired."""
    if cache_key in _recall_cache:
        timestamp, results = _recall_cache[cache_key]
        if time.time() - timestamp < _RECALL_CACHE_TTL:
            return results
        else:
            del _recall_cache[cache_key]
    return None

def _set_cached_recall(cache_key: str, results: List[Dict]) -> None:
    """Set cached recall result."""
    if len(_recall_cache) >= _RECALL_CACHE_MAX_SIZE:
        oldest_key = next(iter(_recall_cache))
        del _recall_cache[oldest_key]
    _recall_cache[cache_key] = (time.time(), results)

def clear_recall_cache() -> None:
    """Clear multi-channel recall cache."""
    global _recall_cache
    _recall_cache.clear()

def multi_channel_recall(
    query: str,
    chroma_client: ChromaClientWrapper,
    bm25_indexes: Dict[str, BM25Indexer],
    top_k_per_channel: int = 8,
    final_top_k: int = 20,
    rrf_k: int = 60,
    vector_weight: float = None,
    inner_top_k: int = 20
) -> List[Dict]:
    """Multi-channel recall: search each collection independently, merge with RRF.

    Args:
        query: Search query
        chroma_client: Chroma client wrapper
        bm25_indexes: Dict mapping collection name to BM25 indexer
        top_k_per_channel: Top-k results from each collection
        final_top_k: Final merged results
        rrf_k: RRF k parameter for reciprocal rank fusion (default 60)
        vector_weight: Weight for vector search in hybrid search (default from config)
        inner_top_k: Number of results to fetch from each search method

    Returns:
        List of merged and ranked results
    """
    # Check cache first
    cache_key = _get_recall_cache_key(query, top_k_per_channel, final_top_k, rrf_k, vector_weight)
    cached_results = _get_cached_recall(cache_key)
    if cached_results is not None:
        return cached_results

    collections = {
        'operators': {'top_k': top_k_per_channel},
        'stories': {'top_k': top_k_per_channel},
        'knowledge': {'top_k': top_k_per_channel},
    }

    all_rankings = []  # List of {chunk_id: rank} dicts for RRF
    all_results = {}  # chunk_id -> result dict

    # Define a function to search a single collection
    def search_collection(coll_name: str, params: Dict):
        if coll_name not in bm25_indexes:
            return None
        try:
            # Use provided vector_weight or default from config
            weight = vector_weight if vector_weight is not None else _VECTOR_WEIGHT
            results = hybrid_search(
                query=query,
                collection_name=coll_name,
                chroma_client=chroma_client,
                bm25_indexer=bm25_indexes[coll_name],
                top_k=params['top_k'],
                vector_weight=weight,
                inner_top_k=inner_top_k
            )
            return coll_name, results
        except Exception as e:
            warnings.warn(f"Error searching collection '{coll_name}': {e}")
            return None

    # Use ThreadPoolExecutor to search collections in parallel
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_coll = {
            executor.submit(search_collection, coll_name, params): coll_name
            for coll_name, params in collections.items()
        }

        for future in as_completed(future_to_coll):
            result = future.result()
            if result is None:
                continue
            coll_name, results = result

            # Add ranking for this collection (1=best)
            for rank, result_item in enumerate(results, 1):
                result_item['source'] = coll_name
                all_results[result_item['chunk_id']] = result_item
                all_rankings.append({result_item['chunk_id']: rank})

    # RRF fusion: score(d) = sum(1 / (k + rank(d))) across all collections
    fused_scores = {}
    for ranking in all_rankings:
        for chunk_id, rank in ranking.items():
            if chunk_id not in fused_scores:
                fused_scores[chunk_id] = 0.0
            fused_scores[chunk_id] += 1.0 / (rrf_k + rank)

    # Sort by fused RRF score
    sorted_results = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)[:final_top_k]

    # Build final results
    final_results = []
    for chunk_id, score in sorted_results:
        result = all_results[chunk_id].copy()
        result['fused_score'] = score
        final_results.append(result)

    # Cache results before returning
    _set_cached_recall(cache_key, final_results)

    return final_results