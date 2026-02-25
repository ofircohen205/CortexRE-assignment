"""
tests/test_asset_manager.py
===========================
Tests covering the core financial logic within AssetManagerAssistant.
"""

import pytest
import pandas as pd
from src.services.portfolio.asset_manager import AssetManagerAssistant


def test_get_property_pl(am: AssetManagerAssistant):
    """Test get_property_pl correctly calculates revenue, expenses, and noi."""
    # Test specific year
    res_2024 = am.get_property_pl("Building A", 2024)
    assert res_2024["revenue"] == 100.0
    assert res_2024["expenses"] == -40.0
    assert res_2024["noi"] == 60.0

    # Test all years aggregated
    res_all = am.get_property_pl("Building A")
    assert res_all["revenue"] == 220.0
    assert res_all["expenses"] == -90.0
    assert res_all["noi"] == 130.0

    # Test missing property returns zeros implicitly handling
    res_missing = am.get_property_pl("Missing Building")
    assert res_missing["revenue"] == 0.0
    assert res_missing["expenses"] == 0.0
    assert res_missing["noi"] == 0.0


def test_get_portfolio_summary(am: AssetManagerAssistant):
    """Test portfolio aggregation across all properties."""
    # Note: "Corporate/General" is explicitly excluded in this mock if it existed,
    # but our conftest sample_df only has Building A and B.
    
    # 2024 Portfolio: A(100 rev, -40 exp), B(200 rev, -90 exp)
    res_2024 = am.get_portfolio_summary(2024)
    assert res_2024["revenue"] == 300.0
    assert res_2024["expenses"] == -130.0
    assert res_2024["noi"] == 170.0

    # All years
    res_all = am.get_portfolio_summary()
    assert res_all["revenue"] == 420.0
    assert res_all["expenses"] == -180.0
    assert res_all["noi"] == 240.0


def test_calculate_oer(am: AssetManagerAssistant):
    """Test Operating Expense Ratio (|expenses| / revenue)."""
    # Building A 2024: |-40| / 100 = 0.40
    oer_a_24 = am.calculate_oer("Building A", 2024)
    assert oer_a_24 == 0.40

    # Building A 2025: |-50| / 120 = ~0.4166
    oer_a_25 = am.calculate_oer("Building A", 2025)
    assert round(oer_a_25, 4) == 0.4167

    # Test protection against zero revenue dividing
    # Build a tiny synthetic df
    zero_rev_am = AssetManagerAssistant(pd.DataFrame([
        {"property_name": "Zero Rev", "year": 2025, "ledger_type": "expenses", "profit": -100.0},
    ]))
    assert zero_rev_am.calculate_oer("Zero Rev", 2025) == 0.0


def test_get_growth_metrics(am: AssetManagerAssistant):
    """Test year-over-year growth calculation."""
    growth = am.get_growth_metrics("noi")
    
    assert "Building A" in growth
    # Building A NOI 2024: 60
    # Building A NOI 2025: 70
    # Growth: (70 - 60) / 60 = 0.166...
    val = growth["Building A"]["2024→2025"]
    assert round(val, 4) == 0.1667
    
    # Building B has no 2025 data in mock df, so val_curr is 0
    # 2024: 110, 2025: 0. Growth = (0 - 110) / 110 = -1.0
    val_b = growth["Building B"]["2024→2025"]
    assert val_b == -1.0


def test_compare_properties(am: AssetManagerAssistant):
    """Test ranking properties by metric."""
    # Compare by revenue (aggregated all years)
    # Building A: 220, Building B: 200
    rev_ranking = am.compare_properties("revenue")
    
    assert rev_ranking.iloc[0] == 220.0
    assert rev_ranking.index[0] == "Building A"
    assert rev_ranking.iloc[1] == 200.0
    assert rev_ranking.index[1] == "Building B"
    
    # Compare by NOI (aggregated all years)
    # Building A: 130, Building B: 110
    noi_ranking = am.compare_properties("noi")
    assert noi_ranking.iloc[0] == 130.0
    assert noi_ranking.index[0] == "Building A"

    with pytest.raises(KeyError):
        am.compare_properties("fake_metric")


def test_compare_properties_excludes_overhead(sample_df):
    """Corporate/General must not appear in the comparison ranking."""
    df_with_overhead = pd.concat([
        sample_df,
        pd.DataFrame([{
            "property_name": "Corporate/General",
            "year": 2024,
            "ledger_type": "expenses",
            "profit": -999.0,
        }]),
    ], ignore_index=True)
    am_with_overhead = AssetManagerAssistant(df_with_overhead)
    result = am_with_overhead.compare_properties("noi")
    assert "Corporate/General" not in result.index


def test_compare_properties_noi_ordering(am):
    """Properties must be sorted descending by the requested metric."""
    result = am.compare_properties("noi")
    values = list(result.values)
    assert values == sorted(values, reverse=True)


def test_top_expense_drivers(sample_df: pd.DataFrame):
    """Test identifying largest expenses."""
    # To test this better, we'll augment our sample df specifically for categories
    df = sample_df.copy()
    df["ledger_category"] = "General"
    
    # Add a huge specific expense
    extra = pd.DataFrame([
        {"property_name": "Building A", "year": 2024, "ledger_type": "expenses", "ledger_category": "Taxes", "profit": -500.0}
    ])
    df = pd.concat([df, extra])
    am = AssetManagerAssistant(df)
    
    # Top expenses portfolio-wide
    top_portfolio = am.top_expense_drivers()
    assert top_portfolio.index[0] == "Taxes"
    assert top_portfolio.iloc[0] == -500.0  # Most negative
    
    # Top expenses Building B (which doesn't have the Taxes row)
    top_b = am.top_expense_drivers("Building B")
    assert top_b.index[0] == "General"
    assert top_b.iloc[0] == -90.0
