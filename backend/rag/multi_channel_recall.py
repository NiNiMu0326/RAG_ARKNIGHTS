import sys
import warnings
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from typing import List, Dict, Tuple
import config
from backend.api.siliconflow import SiliconFlowClient
from backend.storage.chroma_client import ChromaClientWrapper
from backend.data.bm25_index import BM25Indexer
from backend.rag.hybrid_search import hybrid_search, rrf_fusion

def multi_channel_recall(
    query: str,
    chroma_client: ChromaClientWrapper,
    bm25_indexes: Dict[str, BM25Indexer],
    top_k_per_channel: int = 10,
    final_top_k: int = 20
) -> List[Dict]:
    """Multi-channel recall: search each collection independently, merge with RRF.

    Args:
        query: Search query
        chroma_client: Chroma client wrapper
        bm25_indexes: Dict mapping collection name to BM25 indexer
        top_k_per_channel: Top-k results from each collection
        final_top_k: Final merged results

    Returns:
        List of merged and ranked results
    """
    collections = {
        'operators': {'top_k': 10},  # Large collection
        'stories': {'top_k': 10},    # Large collection
        'knowledge': {'top_k': 5},   # Smaller, more diverse
    }

    all_rankings = []  # List of {chunk_id: rank} dicts
    all_results = {}  # chunk_id -> result dict

    for coll_name, params in collections.items():
        if coll_name not in bm25_indexes:
            continue

        try:
            results = hybrid_search(
                query=query,
                collection_name=coll_name,
                chroma_client=chroma_client,
                bm25_indexer=bm25_indexes[coll_name],
                top_k=params['top_k']
            )

            # Add ranking for this collection
            for rank, result in enumerate(results, 1):
                result['source'] = coll_name
                all_results[result['chunk_id']] = result
                # We'll use score-based ranking instead of position-based
                all_rankings.append({result['chunk_id']: (len(results) - rank + 1) / len(results)})

        except Exception as e:
            warnings.warn(f"Error searching collection '{coll_name}': {e}")
            continue

    # RRF fusion across all collections
    # Use normalized scores instead of ranks for better fusion
    fused_scores = {}
    for chunk_id, result in all_results.items():
        if chunk_id not in fused_scores:
            fused_scores[chunk_id] = 0.0
        # Weight by result score
        fused_scores[chunk_id] += result.get('score', 0.0)

    # Sort by fused score
    sorted_results = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)[:final_top_k]

    # Build final results
    final_results = []
    for chunk_id, score in sorted_results:
        result = all_results[chunk_id].copy()
        result['fused_score'] = score
        final_results.append(result)

    return final_results