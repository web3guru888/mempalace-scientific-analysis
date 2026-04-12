import pytest
import asyncio
from unittest.mock import Mock

from mempalace_agi.unified_mcp_server import UnifiedMCPServer

@pytest.fixture
def mock_dependencies():
    palace = Mock()
    engine = Mock()
    kg = Mock()
    config = Mock()
    specialist = Mock()
    return palace, engine, kg, specialist, config

@pytest.mark.asyncio
async def test_mcp_initialization(mock_dependencies):
    server = UnifiedMCPServer(*mock_dependencies)
    
    init_request = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
    response = await server.handle_request(init_request)
    
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "serverInfo" in response["result"]
    assert response["result"]["serverInfo"]["name"] == "mempalace-agi"

@pytest.mark.asyncio
async def test_mcp_tools_list(mock_dependencies):
    server = UnifiedMCPServer(*mock_dependencies)
    
    list_request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
    response = await server.handle_request(list_request)
    
    tools = response["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "astra_run_cycle" in tool_names
    assert "astra_test_hypothesis" in tool_names
    assert "astra_query_discoveries" in tool_names
    assert "astra_get_status" in tool_names
    assert "astra_causal_query" in tool_names
    assert "astra_hypothesis_lifecycle" in tool_names

@pytest.mark.asyncio
async def test_mcp_tools_call(mock_dependencies):
    server = UnifiedMCPServer(*mock_dependencies)
    server.engine.cycle_count = 42
    
    call_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "astra_run_cycle",
            "arguments": {}
        }
    }
    response = await server.handle_request(call_request)
    
    assert response["jsonrpc"] == "2.0"
    result_text = response["result"]["content"][0]["text"]
    assert "42" in result_text
    server.engine.run_cycle.assert_called_once()


# ---- Schema-based argument filtering tests ----

class TestSchemaArgFiltering:
    """Tests for _filter_args_by_schema — defence against non-standard MCP client args."""

    def test_filter_strips_undeclared_keys(self):
        schema = {"properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}}
        args = {"query": "hello", "limit": 10, "wait_for_previous": True, "bogus": 42}
        result = UnifiedMCPServer._filter_args_by_schema(args, schema, "test_tool")
        assert result == {"query": "hello", "limit": 10}
        # Original dict should be unchanged
        assert "wait_for_previous" in args

    def test_filter_preserves_all_declared_keys(self):
        schema = {"properties": {"a": {}, "b": {}, "c": {}}}
        args = {"a": 1, "b": 2, "c": 3}
        result = UnifiedMCPServer._filter_args_by_schema(args, schema, "test_tool")
        assert result is args  # same object when nothing stripped
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_filter_handles_empty_args(self):
        schema = {"properties": {"x": {}}}
        result = UnifiedMCPServer._filter_args_by_schema({}, schema, "test_tool")
        assert result == {}

    def test_filter_handles_empty_schema(self):
        """Tool with no declared properties — all args should be stripped."""
        schema = {"properties": {}}
        args = {"rogue_key": "value"}
        result = UnifiedMCPServer._filter_args_by_schema(args, schema, "test_tool")
        assert result == {}

    def test_filter_handles_missing_properties_key(self):
        """Schema without a properties key — should not crash."""
        schema = {}
        args = {"anything": 123}
        result = UnifiedMCPServer._filter_args_by_schema(args, schema, "test_tool")
        assert result == {}


@pytest.mark.asyncio
async def test_schema_filtering_in_astra_tool_dispatch(mock_dependencies):
    """End-to-end: non-standard args stripped before ASTRA handler dispatch."""
    server = UnifiedMCPServer(*mock_dependencies)
    server.engine.cycle_count = 7

    call_request = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {
            "name": "astra_run_cycle",
            "arguments": {
                "force_domain": "astro",
                "wait_for_previous": True,       # Gemini injects this
                "some_future_field": "whatever",  # hypothetical future client injection
            }
        }
    }
    response = await server.handle_request(call_request)

    # Should succeed — the rogue keys must not cause TypeError
    assert response["jsonrpc"] == "2.0"
    assert "result" in response
    result_text = response["result"]["content"][0]["text"]
    assert "7" in result_text
    server.engine.run_cycle.assert_called_once()


@pytest.mark.asyncio
async def test_schema_filtering_with_type_coercion(mock_dependencies):
    """Schema filtering + type coercion work together."""
    server = UnifiedMCPServer(*mock_dependencies)
    server.palace_memory.semantic_search.return_value = [{"id": "d1", "strength": 0.9}]

    call_request = {
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {
            "name": "astra_query_discoveries",
            "arguments": {
                "query": "dark matter",
                "limit": "5",                   # string that needs int coercion
                "wait_for_previous": True,       # should be stripped
            }
        }
    }
    response = await server.handle_request(call_request)

    assert "result" in response
    # Verify the handler got the coerced int, not the string
    server.palace_memory.semantic_search.assert_called_once_with(
        query="dark matter", domain=None, n_results=5
    )
