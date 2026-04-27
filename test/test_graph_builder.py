"""
Tests for backend.rag.graphrag.builder: GraphBuilder.
Usage: cd test && python -m pytest test_graph_builder.py -v
"""
import sys
import json
import tempfile
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.rag.graphrag.builder import GraphBuilder


@pytest.fixture
def sample_data(tmp_path):
    """Create a temporary entity_relations.json and return a GraphBuilder pointing at it."""
    data = {
        "entities": {
            "干员": ["银灰", "初雪", "崖心"],
            "组织": ["喀兰贸易", "罗德岛"],
        },
        "relations": [
            {"source": "银灰", "target": "初雪", "relation": "兄妹", "description": "银灰是初雪的哥哥"},
            {"source": "银灰", "target": "崖心", "relation": "兄妹", "description": "银灰是崖心的哥哥"},
            {"source": "银灰", "target": "喀兰贸易", "relation": "隶属于", "description": "银灰是喀兰贸易领袖"},
            {"source": "初雪", "target": "喀兰贸易", "relation": "隶属于", "description": ""},
            {"source": "崖心", "target": "罗德岛", "relation": "合作", "description": "崖心在罗德岛接受治疗"},
        ]
    }
    filepath = tmp_path / "entity_relations.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return GraphBuilder(entity_relations_path=str(filepath))


class TestGraphBuilder:
    def test_build_basic(self, sample_data):
        gb = sample_data
        g = gb.build()
        assert g.number_of_nodes() == 5
        assert g.number_of_edges() == 5

    def test_build_nodes_have_types(self, sample_data):
        gb = sample_data
        g = gb.build()
        assert g.nodes["银灰"]["type"] == "干员"
        assert g.nodes["喀兰贸易"]["type"] == "组织"

    def test_build_is_idempotent(self, sample_data):
        gb = sample_data
        g1 = gb.build()
        g2 = gb.build()
        assert g1 is g2  # Returns cached graph

    def test_force_rebuild(self, sample_data):
        gb = sample_data
        g1 = gb.build()
        g2 = gb.build(force=True)
        assert g1 is not g2  # Different object

    def test_get_neighbors(self, sample_data):
        gb = sample_data
        gb.build()
        neighbors = gb.get_neighbors("银灰")
        assert len(neighbors) == 3  # 初雪, 崖心, 喀兰贸易
        entities = {n["entity"] for n in neighbors}
        assert entities == {"初雪", "崖心", "喀兰贸易"}

    def test_get_neighbors_incoming(self, sample_data):
        gb = sample_data
        gb.build()
        neighbors = gb.get_neighbors("喀兰贸易")
        # Has incoming edges from 银灰 and 初雪
        assert len(neighbors) == 2
        directions = {n["direction"] for n in neighbors}
        assert "incoming" in directions

    def test_get_neighbors_nonexistent(self, sample_data):
        gb = sample_data
        gb.build()
        assert gb.get_neighbors("不存在的实体") == []

    def test_get_all_relations(self, sample_data):
        gb = sample_data
        gb.build()
        rels = gb.get_all_relations("银灰")
        assert len(rels["outgoing"]) == 3
        assert len(rels["incoming"]) == 0

    def test_find_path(self, sample_data):
        gb = sample_data
        gb.build()
        result = gb.find_path("银灰", "罗德岛")
        assert result["path"] == ["银灰", "崖心", "罗德岛"]
        assert len(result["edges"]) == 2

    def test_find_path_self(self, sample_data):
        gb = sample_data
        gb.build()
        result = gb.find_path("银灰", "银灰")
        assert result["path"] == ["银灰"]
        assert result["edges"] == []

    def test_find_path_nonexistent(self, sample_data):
        gb = sample_data
        gb.build()
        result = gb.find_path("银灰", "不存在")
        assert result["path"] == []
        assert result["edges"] == []

    def test_find_path_disconnected(self, sample_data):
        """Two entities not connected by any path."""
        gb = sample_data
        g = gb.build()
        # Add isolated node
        g.add_node("孤立节点", type="干员")
        result = gb.find_path("银灰", "孤立节点")
        assert result["path"] == []

    def test_save_and_load(self, sample_data, tmp_path):
        gb = sample_data
        gb.build()
        save_path = tmp_path / "graph.gml"
        gb.save(str(save_path))
        assert save_path.exists()

        loaded = GraphBuilder.load(str(save_path))
        g = loaded.graph
        assert g is not None
        assert g.number_of_nodes() == 5
        assert g.number_of_edges() == 5
