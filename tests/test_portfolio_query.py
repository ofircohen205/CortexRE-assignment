import pandas as pd
from src.services.portfolio.asset_manager import AssetManagerAssistant

def test_query_portfolio_no_dimensions(am: AssetManagerAssistant):
    """Test when no dimensions are provided, it should aggregate the entire dataset."""
    result = am.query_portfolio(dimensions=[])
    
    assert len(result) == 1
    # 100 - 40 + 120 - 50 + 200 - 90 = 240
    assert result[0]["profit"] == 240.0


def test_query_portfolio_single_dimension(am: AssetManagerAssistant):
    """Test grouping by a single dimension (year)."""
    result = am.query_portfolio(dimensions=["year"])
    
    assert len(result) == 2
    
    # 2024: 100 - 40 + 200 - 90 = 170
    year_2024 = next(r for r in result if r["year"] == 2024)
    assert year_2024["profit"] == 170.0
    
    # 2025: 120 - 50 = 70
    year_2025 = next(r for r in result if r["year"] == 2025)
    assert year_2025["profit"] == 70.0


def test_query_portfolio_multiple_dimensions(am: AssetManagerAssistant):
    """Test grouping by multiple dimensions (property_name and ledger_type)."""
    result = am.query_portfolio(dimensions=["property_name", "ledger_type"])
    
    assert len(result) == 4
    
    bldg_a_rev = next(r for r in result if r["property_name"] == "Building A" and r["ledger_type"] == "revenue")
    # Building A revenue: 100 (2024) + 120 (2025) = 220
    assert bldg_a_rev["profit"] == 220.0


def test_query_portfolio_with_filter(am: AssetManagerAssistant):
    """Test filtering before grouping."""
    result = am.query_portfolio(
        dimensions=["property_name"],
        filters=[{"column": "year", "value": 2025}]
    )
    
    # Only Building A has 2025 data in the mock
    assert len(result) == 1
    assert result[0]["property_name"] == "Building A"
    assert result[0]["profit"] == 70.0  # 120 - 50


def test_query_portfolio_invalid_dimensions_ignored(am: AssetManagerAssistant):
    """Test that dimensions not present in the dataframe are safely ignored."""
    result = am.query_portfolio(dimensions=["property_name", "fake_column"])
    
    # Should group by property_name only since fake_column is ignored
    assert len(result) == 2
    
    bldg_a = next(r for r in result if r["property_name"] == "Building A")
    assert bldg_a["profit"] == 130.0  # (100 - 40) + (120 - 50)


def test_query_portfolio_invalid_filter_ignored(am: AssetManagerAssistant):
    """Test that filters on invalid columns are safely ignored."""
    result = am.query_portfolio(
        dimensions=["year"],
        filters=[{"column": "fake_column", "value": "some_value"}]
    )
    
    # The filter shouldn't apply, so it returns all years
    assert len(result) == 2
    
def test_query_portfolio_empty_result_on_filter(am: AssetManagerAssistant):
    """Test that an overly restrictive filter returns an empty list or empty aggregation."""
    result = am.query_portfolio(
        dimensions=["property_name"],
        filters=[{"column": "year", "value": 2099}]
    )
    
    assert len(result) == 0
