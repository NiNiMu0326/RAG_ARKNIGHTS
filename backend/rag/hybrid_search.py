import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from typing import List, Dict, Tuple
import config
from backend.api.siliconflow import SiliconFlowClient
from backend.storage.chroma_client import ChromaClientWrapper
from backend.data.bm25_index import BM25Indexer

RRF_K = config.RRF_K  # 60

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
    vector_weight: float = 0.5,
    top_k: int = 10
) -> List[Dict]:
    """Perform hybrid search on a single collection using vector + BM25 + RRF.

    Returns list of dicts with chunk_id, content, metadata, score, source
    """
    # 1. Vector search (top 20) - embed query explicitly
    try:
        vector_results = chroma_client.search(collection_name, query, n_results=20)
    except:
        vector_results = []

    # 2. BM25 search (top 20)
    bm25_chunk_ids = bm25_indexer.retrieve(query, top_k=20)
    bm25_results = []
    if bm25_indexer.corpus and bm25_indexer.chunk_ids:
        # Create mapping from chunk_id to index
        chunk_id_to_idx = {chunk_id: idx for idx, chunk_id in enumerate(bm25_indexer.chunk_ids)}
        for chunk_id in bm25_chunk_ids:
            idx = chunk_id_to_idx.get(chunk_id)
            if idx is not None and idx < len(bm25_indexer.corpus):
                bm25_results.append({
                    'chunk_id': chunk_id,
                    'content': bm25_indexer.corpus[idx]
                })

    # 3. Build rankings for RRF
    # Vector ranking (1=best)
    vector_ranking = {r['chunk_id']: i+1 for i, r in enumerate(vector_results) if r.get('content')}
    # BM25 ranking (1=best)
    bm25_ranking = {r['chunk_id']: i+1 for i, r in enumerate(bm25_results) if r.get('content')}

    # 4. RRF fusion
    all_doc_ids = set(vector_ranking.keys()) | set(bm25_ranking.keys())

    # Get top-k using weighted combination
    combined_scores = {}
    for doc_id in all_doc_ids:
        vec_score = 1.0 / (RRF_K + vector_ranking.get(doc_id, RRF_K + 100))
        bm25_score = 1.0 / (RRF_K + bm25_ranking.get(doc_id, RRF_K + 100))
        combined_scores[doc_id] = vector_weight * vec_score + (1 - vector_weight) * bm25_score

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

        if doc_id in all_vector_results:
            content = all_vector_results[doc_id].get('content', '')
            metadata = all_vector_results[doc_id].get('metadata', {})
            distance = all_vector_results[doc_id].get('distance', 0.0)
        elif doc_id in all_bm25_results:
            content = all_bm25_results[doc_id].get('content', '')

        results.append({
            'chunk_id': doc_id,
            'content': content,
            'metadata': metadata,
            'score': score,
            'distance': distance,
            'source': collection_name
        })

    return results