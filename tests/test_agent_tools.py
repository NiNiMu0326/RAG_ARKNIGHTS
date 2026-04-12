"""
Tests for backend.agent.tools - Tool schemas and ToolRegistry.
"""
import pytest
from backend.agent.tools import TOOL_SCHEMAS, ToolRegistry


class TestToolSchemas:
    def test_three_tools_defined(self):
        assert len(TOOL_SCHEMAS) == 3

    def test_tool_names(self):
        names = [t["function"]["name"] for t in TOOL_SCHEMAS]
        assert "arknights_rag_search" in names
        assert "arknights_graphrag_search" in names
        assert "web_search" in names

    def test_rag_search_required_params(self):
        rag_schema = next(t for t in TOOL_SCHEMAS if t["function"]["name"] == "arknights_rag_search")
        assert "query" in rag_schema["function"]["parameters"]["required"]

    def test_graphrag_search_no_required_params(self):
        graph_schema = next(t for t in TOOL_SCHEMAS if t["function"]["name"] == "arknights_graphrag_search")
        assert "required" not in graph_schema["function"]["parameters"] or \
               len(graph_schema["function"]["parameters"].get("required", [])) == 0

    def test_web_search_required_params(self):
        web_schema = next(t for t in TOOL_SCHEMAS if t["function"]["name"] == "web_search")
        assert "query" in web_schema["function"]["parameters"]["required"]

    def test_all_tools_have_descriptions(self):
        for schema in TOOL_SCHEMAS:
            assert len(schema["function"]["description"]) > 10


class TestToolRegistry:
    def test_register_and_execute(self):
        registry = ToolRegistry()
        called_with = {}

        async def mock_executor(args):
            called_with.update(args)
            return "mock_result"

        registry.register("test_tool", mock_executor)
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            registry.execute("test_tool", {"key": "value"})
        )
        assert result == "mock_result"
        assert called_with == {"key": "value"}

    def test_execute_unknown_tool(self):
        registry = ToolRegistry()
        import asyncio
        with pytest.raises(ValueError, match="Unknown tool"):
            asyncio.get_event_loop().run_until_complete(
                registry.execute("nonexistent", {})
            )

    def test_get_schemas_returns_tool_schemas(self):
        registry = ToolRegistry()
        schemas = registry.get_schemas()
        assert schemas == TOOL_SCHEMAS
