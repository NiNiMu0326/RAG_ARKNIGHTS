import sys
import warnings
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from typing import List, Dict, Optional, Tuple
from backend.api.siliconflow import SiliconFlowClient
from backend.rag.graphrag.builder import GraphBuilder

# Module-level singleton for GraphBuilder
_graph_builder_instance: Optional[GraphBuilder] = None

def get_graph_builder() -> GraphBuilder:
    """Get or create singleton GraphBuilder instance."""
    global _graph_builder_instance
    if _graph_builder_instance is None:
        _graph_builder_instance = GraphBuilder()
        try:
            _graph_builder_instance.build()
        except FileNotFoundError:
            warnings.warn("GraphRAG entity_relations.json not found. Relationship queries will be unavailable.")
        except Exception as e:
            warnings.warn(f"Failed to build GraphRAG knowledge graph: {e}")
    return _graph_builder_instance

RELATION_DETECTION_PROMPT = """你是一个问题分析专家。请判断用户问题是否在询问干员之间的关系。

## 任务
判断以下问题是否在询问两个或多个干员之间的关系（如"银灰和初雪什么关系"、"谁是银灰的妹妹"等）

## 判断标准
以下情况视为询问关系：
- 明确提到两个或多个干员名，询问他们之间的关系
- 使用"谁是X的XX"、"X和Y有什么关系"等句式
- 询问干员的家族关系、阵营关系、合作/对抗关系等

以下情况不视为询问关系：
- 询问单个干员的属性（技能、天赋、数值等）
- 询问游戏机制、攻略等

## 用户问题
{question}

## 输出
如果问题是询问关系，输出"YES"和所有提到的干员名称（用逗号分隔）
如果问题不是询问关系，输出"NO"

格式：
YES: 银灰, 初雪
或者
NO
"""

class GraphRAGQuery:
    def __init__(self, api_key: str = None, graph_path: str = None):
        self.client = SiliconFlowClient(api_key)
        self.graph_builder = get_graph_builder()

    def is_relation_query(self, question: str) -> Tuple[bool, List[str]]:
        """Detect if question is asking about operator relationships."""
        try:
            response = self.client.chat([
                {"role": "system", "content": "你是一个问题分析专家。直接输出YES或NO，不要解释。"},
                {"role": "user", "content": RELATION_DETECTION_PROMPT.format(question=question)}
            ])

            response = response.strip()
            if response.startswith('YES'):
                # Extract operator names after "YES:"
                parts = response.split(':', 1)
                if len(parts) > 1:
                    names = [n.strip() for n in parts[1].split(',')]
                    return True, names
                return True, []
            return False, []
        except Exception as e:
            warnings.warn(f"Failed to detect relation query: {e}")
            return False, []

    def query(self, question: str) -> Dict:
        """Query the knowledge graph for operator relationships."""
        # Check if this is a relation query
        is_relation, operators = self.is_relation_query(question)

        if not is_relation or not operators:
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