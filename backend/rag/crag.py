import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class CRAGStrategy:
    level: str  # HIGH, MEDIUM, LOW
    avg_score: float
    should_search_web: bool
    should_use_docs: bool
    num_low_score_docs: int  # Number of docs below threshold
    web_search_count: int  # How many web results to search (N*2)
    reasoning: str


class CRAGJudge:
    def __init__(self):
        self.high_threshold = 0.7  # Average score threshold for HIGH
        self.doc_threshold = 0.4   # Per-document threshold

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

        # Determine level based on average score
        if avg_score >= self.high_threshold:
            # HIGH: Even if some low docs exist, high average means overall relevant
            return CRAGStrategy(
                level='HIGH',
                avg_score=avg_score,
                should_search_web=False,
                should_use_docs=True,
                num_low_score_docs=num_low,
                web_search_count=0,
                reasoning=f"HIGH: avg_score={avg_score:.3f} >= 0.7, using all local docs"
            )

        # MEDIUM or LOW: Need to supplement with web search
        if avg_score < 0.4:
            level = 'LOW'
        else:
            level = 'MEDIUM'

        # N = number of docs below threshold, search N*2
        web_count = num_low * 2

        return CRAGStrategy(
            level=level,
            avg_score=avg_score,
            should_search_web=True,
            should_use_docs=True,
            num_low_score_docs=num_low,
            web_search_count=web_count,
            reasoning=f"{level}: avg_score={avg_score:.3f}, {num_low} docs below {self.doc_threshold}, will search {web_count} web results"
        )
