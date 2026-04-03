import json
import networkx as nx
from typing import Dict, List, Set, Optional
from pathlib import Path

class GraphBuilder:
    def __init__(self, entity_relations_path: str = None):
        if entity_relations_path:
            self.entity_relations_path = entity_relations_path
        else:
            # Use config to get the correct path
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from backend.config import ENTITY_RELATIONS_FILE
            self.entity_relations_path = str(ENTITY_RELATIONS_FILE)
        self.graph = None

    def build(self, force: bool = False) -> nx.Graph:
        """Build NetworkX graph from entity relations."""
        if self.graph is not None and not force:
            return self.graph

        self.graph = nx.Graph()

        if not Path(self.entity_relations_path).exists():
            print(f"Entity relations file not found: {self.entity_relations_path}")
            print("Run python -m src.rag.graphrag.extractor first to build the graph.")
            return self.graph

        with open(self.entity_relations_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Add nodes (entities)
        for entity in data.get('entities', []):
            self.graph.add_node(entity['entity'], type=entity.get('type', '干员'))

        # Add edges (relations)
        for relation in data.get('relations', []):
            self.graph.add_edge(
                relation['source'],
                relation['target'],
                relation=relation.get('relation', ''),
                description=relation.get('description', '')
            )

        print(f"Built graph: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
        return self.graph

    def get_neighbors(self, entity: str, depth: int = 1) -> List[Dict]:
        """Get neighboring entities and their relations."""
        if self.graph is None:
            self.build()

        if entity not in self.graph:
            return []

        neighbors = []
        for neighbor in self.graph.neighbors(entity):
            edge_data = self.graph[entity][neighbor]
            neighbors.append({
                'entity': neighbor,
                'relation': edge_data.get('relation', ''),
                'description': edge_data.get('description', '')
            })

        return neighbors

    def get_all_relations(self, entity: str) -> Dict:
        """Get all relations for an entity."""
        if self.graph is None:
            self.build()

        if entity not in self.graph:
            return {'incoming': [], 'outgoing': []}

        incoming = []
        outgoing = []

        for neighbor in self.graph.neighbors(entity):
            edge_data = self.graph[entity][neighbor]
            rel_info = {
                'entity': neighbor,
                'relation': edge_data.get('relation', ''),
                'description': edge_data.get('description', '')
            }
            # Since graph is undirected, we just track both directions
            incoming.append(rel_info)
            outgoing.append(rel_info)

        return {'incoming': incoming, 'outgoing': outgoing}

    def find_path(self, entity1: str, entity2: str) -> List[str]:
        """Find shortest path between two entities."""
        if self.graph is None:
            self.build()

        try:
            return nx.shortest_path(self.graph, entity1, entity2)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def save(self, path: str):
        """Save graph to file."""
        if self.graph is None:
            return
        nx.write_gml(self.graph, path)
        print(f"Saved graph to {path}")

    @classmethod
    def load(cls, path: str) -> 'GraphBuilder':
        """Load graph from file."""
        builder = cls()
        builder.graph = nx.read_gml(path)
        return builder