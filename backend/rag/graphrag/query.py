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


