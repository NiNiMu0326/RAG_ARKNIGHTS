import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from typing import List, Dict
from dataclasses import dataclass
from langchain_core.documents import Document
from backend import config


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


from langchain_core.runnables import RunnableLambda
from typing import Dict as TypingDict

def make_crag_runnable(use_crag: bool = True) -> RunnableLambda:
    """Create a RunnableLambda that wraps CRAGJudge.judge().

    Input state: {..., "reranked_docs": List[Document]}
    Output state: same + {"crag": CRAGStrategy}
    """
    judge = CRAGJudge()
    # Capture use_crag at definition time
    _use_crag = use_crag

    def _judge(state: TypingDict) -> TypingDict:
        import time as _time
        t0 = _time.time()
        reranked_docs = state.get("reranked_docs", [])
        # Also check config for use_crag flag
        config_use_crag = state.get("config", {}).get("use_crag", _use_crag)

        # Convert Document list to dict list expected by CRAGJudge
        doc_dicts = []
        for doc in reranked_docs:
            if isinstance(doc, Document):
                doc_dicts.append({"relevance_score": doc.metadata.get("relevance_score", 0.0)})
            elif isinstance(doc, dict):
                doc_dicts.append({"relevance_score": doc.get("relevance_score", 0.0)})
            elif isinstance(doc, str):
                doc_dicts.append({"relevance_score": 0.0})

        if config_use_crag and doc_dicts:
            strategy = judge.judge(doc_dicts)
        else:
            avg_score = (
                sum(d["relevance_score"] for d in doc_dicts) / len(doc_dicts)
                if doc_dicts else 0.0
            )
            strategy = CRAGStrategy(
                level="HIGH",
                avg_score=avg_score,
                should_search_web=False,
                should_use_docs=True,
                num_low_score_docs=0,
                web_search_count=0,
                reasoning="CRAG disabled" if not config_use_crag else "No docs",
            )
        elapsed = round((_time.time() - t0) * 1000)
        timings = state.get("_step_timings", {})
        timings["crag"] = elapsed
        return {**state, "crag": strategy, "_step_timings": timings}

    return RunnableLambda(_judge, name="CRAGJudge")
