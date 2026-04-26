import sys
import warnings
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from typing import List, Dict, Optional
from backend.rag.graphrag.builder import GraphBuilder

# Module-level singleton for GraphBuilder
_graph_builder_instance: Optional[GraphBuilder] = None
_graph_builder_lock = threading.Lock()

def get_graph_builder() -> GraphBuilder:
    """Get or create singleton GraphBuilder instance (thread-safe)."""
    global _graph_builder_instance
    if _graph_builder_instance is None:
        with _graph_builder_lock:
            # Double-check locking pattern
            if _graph_builder_instance is None:
                _graph_builder_instance = GraphBuilder()
                try:
                    _graph_builder_instance.build()
                except FileNotFoundError:
                    warnings.warn("GraphRAG entity_relations.json not found. Relationship queries will be unavailable.")
                except Exception as e:
                    warnings.warn(f"Failed to build GraphRAG knowledge graph: {e}")
    return _graph_builder_instance


class GraphRAGQuery:
    def __init__(self):
        self.graph_builder = get_graph_builder()

    def query_with_flags(self, question: str, is_relation_query: bool, detected_operators: List[str] = None) -> Dict:
        """Query the knowledge graph with pre-determined relation query flags.

        This method uses the is_relation_query and detected_operators from QueryRewriter,
        avoiding any LLM calls for relation detection.

        Args:
            question: User question
            is_relation_query: Pre-determined by QueryRewriter
            detected_operators: List of operators to query (from QueryRewriter)

        Returns:
            Dict with is_relation_query and results
        """
        if not is_relation_query:
            return {
                'is_relation_query': False,
                'results': []
            }

        operators = detected_operators
        if not operators:
            return {
                'is_relation_query': False,
                'results': []
            }

        # Query graph for each operator
        all_results = []
        for op in operators:
            neighbors = self.graph_builder.get_neighbors(op)
            for neighbor in neighbors:
                all_results.append({
                    'operator1': op,
                    'operator2': neighbor['entity'],
                    'relation': neighbor['relation'],
                    'description': neighbor['description']
                })

        return {
            'is_relation_query': True,
            'detected_operators': operators,
            'results': all_results
        }
