"""
Tool definitions and execution for AgenticRAG.
Defines tool schemas and dispatches tool calls to implementations.
"""

import json
import logging
from typing import Dict, List, Any, Optional, Callable

logger = logging.getLogger(__name__)


# ===== Tool Schemas (OpenAI Function Calling format) =====

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "arknights_rag_search",
            "description": "在明日方舟知识库中检索相关文档内容。适用于查询干员技能、属性、剧情、关卡攻略等知识库中存在的内容。返回文档片段及相关性分数。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词或问题"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回结果数量，默认5"
                    }
                },
                "required": ["query"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "arknights_graphrag_search",
            "description": "查询明日方舟实体（干员、组织、地点、事件）之间的关系。支持两种模式：\n1. 传入 entity（一个实体）：返回该实体的所有直接邻居及关系\n2. 传入 entity1 + entity2（两个实体）：返回两实体间的最短关系路径（可能经过多个中间节点），以及路径上每条边的关系和描述\n\n适用于需要了解角色血缘、所属组织、战友关系，或发现间接关系。",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "要查询的实体名称（单实体模式）"
                    },
                    "entity1": {
                        "type": "string",
                        "description": "起始实体名称（双实体路径模式）"
                    },
                    "entity2": {
                        "type": "string",
                        "description": "目标实体名称（双实体路径模式）"
                    }
                },
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "在互联网上搜索信息。当知识库中没有足够信息，或需要最新资讯时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词"
                    }
                },
                "required": ["query"],
                "additionalProperties": False
            }
        }
    }
]


# ===== Tool Registry =====

class ToolRegistry:
    """Registry that maps tool names to their executor functions."""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}

    def register(self, name: str, executor: Callable):
        """Register a tool executor function."""
        self._tools[name] = executor
        logger.info(f"Registered tool: {name}")

    def get_schemas(self) -> List[Dict]:
        """Get all tool schemas for API calls."""
        return TOOL_SCHEMAS

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool by name with the given arguments."""
        executor = self._tools.get(tool_name)
        if executor is None:
            raise ValueError(f"Unknown tool: {tool_name}")

        return await executor(arguments)


# ===== Singleton Registry =====

_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get or create the global tool registry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        _register_default_tools(_registry)
    return _registry


def _register_default_tools(registry: ToolRegistry):
    """Register the default RAG tools."""
    from backend.agent.tool_implementations import (
        execute_rag_search,
        execute_graphrag_search,
        execute_web_search,
    )
    registry.register("arknights_rag_search", execute_rag_search)
    registry.register("arknights_graphrag_search", execute_graphrag_search)
    registry.register("web_search", execute_web_search)
