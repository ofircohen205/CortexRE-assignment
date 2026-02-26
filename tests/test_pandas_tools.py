"""
tests/test_pandas_tools.py
==========================
Tests covering the LangChain tool wrappers inside pandas_tools.py.
"""

import pytest
from src.agents.tools.pandas_tools import create_tools

def test_create_tools(sample_df):
    """Test that all tools are successfully instantiated and receive their docstrings."""
    tools = create_tools(sample_df)

    # We have 10 tools in the list (list_properties, get_property_pl, query_portfolio, get_schema_info, get_tenant_summary, etc)
    assert len(tools) == 10

    tool_names = [t.name for t in tools]

    assert "list_properties_tool" in tool_names
    assert "get_property_pl" in tool_names
    assert "get_portfolio_summary" in tool_names
    assert "calculate_oer" in tool_names
    assert "get_growth_metrics" in tool_names
    assert "compare_properties" in tool_names
    assert "top_expense_drivers" in tool_names
    assert "query_portfolio" in tool_names
    assert "get_schema_info" in tool_names
    
    # Check that docstrings were properly parsed for the LLM
    query_tool = next(t for t in tools if t.name == "query_portfolio")
    assert query_tool.description is not None
    assert "Flexible query engine" in query_tool.description
    
    # Verify the schema parsing (arguments mapping)
    schema_keys = query_tool.args.keys()
    assert "dimensions" in schema_keys
    assert "metrics" in schema_keys
    assert "filters" in schema_keys


def test_list_properties_tool(sample_df):
    """Test the list_properties tool specifically since it doesn't just pass through AssetManager."""
    tools = create_tools(sample_df)
    list_tool = next(t for t in tools if t.name == "list_properties_tool")

    # In our mock dataframe we have "Building A" and "Building B"
    result = list_tool.invoke({})

    assert result["count"] == 2
    assert "Building A" in result["properties"]
    assert "Building B" in result["properties"]


def test_get_tenant_summary_all(sample_df):
    """get_tenant_summary with no filters returns all tenants."""
    tools = {t.name: t for t in create_tools(sample_df)}
    result = tools["get_tenant_summary"].invoke({})
    assert "rows" in result
    assert len(result["rows"]) > 0
    assert result["top_tenant"] is not None


def test_get_tenant_summary_by_property(sample_df):
    """get_tenant_summary scoped to a property only returns that property's tenants."""
    tools = {t.name: t for t in create_tools(sample_df)}
    result = tools["get_tenant_summary"].invoke({"property_name": "Building A"})
    assert "rows" in result
    for row in result["rows"]:
        assert row["property_name"] == "Building A"


def test_get_tenant_summary_unknown_property_raises(sample_df):
    """get_tenant_summary with an unknown property raises ToolError."""
    from src.agents.tools.pandas_tools import ToolError
    tools = {t.name: t for t in create_tools(sample_df)}
    with pytest.raises(ToolError):
        tools["get_tenant_summary"].invoke({"property_name": "Nonexistent Building"})
