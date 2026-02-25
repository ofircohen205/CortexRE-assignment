"""
tests/test_pandas_tools.py
==========================
Tests covering the LangChain tool wrappers inside pandas_tools.py.
"""

from src.agents.tools.pandas_tools import create_tools

def test_create_tools(sample_df):
    """Test that all tools are successfully instantiated and receive their docstrings."""
    tools = create_tools(sample_df)
    
    # We have 9 tools in the list (list_properties, get_property_pl, query_portfolio, get_schema_info, etc)
    assert len(tools) == 9

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
