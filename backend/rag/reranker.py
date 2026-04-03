import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from typing import List, Dict
from backend.api.siliconflow import SiliconFlowClient

class Reranker:
    def __init__(self, api_key: str = None):
        self.client = SiliconFlowClient(api_key)

    def rerank(self, query: str, documents: List[str], top_k: int = 5) -> List[Dict]:
        """Rerank documents using cross-encoder.

        Args:
            query: Search query
            documents: List of document texts to rerank
            top_k: Number of top results to return

        Returns:
            List of dicts with index, relevance_score, document
        """
        if not documents:
            return []

        # Call SiliconFlow rerank API
        results = self.client.rerank(query, documents)

        # Format results
        formatted = []
        for r in results:
            idx = r.get('index', 0)
            if idx < len(documents):
                formatted.append({
                    'index': idx,
                    'relevance_score': r.get('relevance_score', 0.0),
                    'document': documents[idx],
                    'original_rank': idx + 1
                })

        # Sort by relevance score descending and take top_k
        formatted.sort(key=lambda x: x['relevance_score'], reverse=True)
        return formatted[:top_k]