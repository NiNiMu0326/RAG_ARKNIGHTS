import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from typing import List, Dict, Tuple
from dataclasses import dataclass
import config


@dataclass
class CRAGStrategy:
    level: str  # HIGH, LOW
    avg_score: float
    should_search_web: bool
    should_use_docs: bool
    num_low_score_docs: int
    web_search_count: int
    reasoning: str


class CRAGJudge:
    def __init__(self):
        self.high_threshold = getattr(config, 'CRAG_HIGH_THRESHOLD', 0.6)
        self.doc_threshold = getattr(config, 'CRAG_LOW_THRESHOLD', 0.4)

    def judge(self, reranked_results: List[Dict]) -> CRAGStrategy:
        """Judge the quality of retrieval results.

        Args:
            reranked_results: List of dicts with relevance_score

        Returns:
            CRAGStrategy with level and action flags
        """
        if not reranked_results:
            return CRAGStrategy(
                level='LOW',
                avg_score=0.0,
                should_search_web=True,
                should_use_docs=False,
                num_low_score_docs=0,
                web_search_count=0,
                reasoning="No results retrieved"
            )

        # Calculate average score
        scores = [r.get('relevance_score', 0.0) for r in reranked_results]
        avg_score = sum(scores) / len(scores)

        # Count docs below threshold
        low_score_docs = [s for s in scores if s < self.doc_threshold]
        num_low = len(low_score_docs)

        # Two-level classification: HIGH (>=0.6) or LOW (<0.6)
        if avg_score >= self.high_threshold:
            return CRAGStrategy(
                level='HIGH',
                avg_score=avg_score,
                should_search_web=False,
                should_use_docs=True,
                num_low_score_docs=num_low,
                web_search_count=0,
                reasoning=f"HIGH: avg_score={avg_score:.3f} >= 0.6, using local docs only"
            )

        # LOW: Need to supplement with web search
        web_count = num_low * 2

        return CRAGStrategy(
            level='LOW',
            avg_score=avg_score,
            should_search_web=True,
            should_use_docs=True,
            num_low_score_docs=num_low,
            web_search_count=web_count,
            reasoning=f"LOW: avg_score={avg_score:.3f}, {num_low} docs below {self.doc_threshold}, will search {web_count} web results"
        )
