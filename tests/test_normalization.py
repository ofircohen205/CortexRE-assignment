"""
tests/test_normalization.py
===========================
Tests for the raw dataset normalization pipeline.
"""

import pandas as pd
import numpy as np
import pytest
from src.services.portfolio.normalization import normalize_data, OVERHEAD_PROPERTY


@pytest.fixture
def raw_df() -> pd.DataFrame:
    """Mock raw DataFrame resembling the unwieldy input data."""
    data = [
        {
            "month": "2025-M01",
            "quarter": "2025-Q1",
            "property_name": "  Building A  ",
            "tenant_name": None,
            "ledger_description": "Loyer de base | Base Rent",
            "profit": 1000.0,
            "ledger_type": "revenue",
        },
        {
            "month": "2024-M12",
            "quarter": "2024-Q4",
            "property_name": None,
            "tenant_name": "  Acme Corp  ",
            "ledger_description": "Taxes | Property Taxes",
            "profit": -500.0,
            "ledger_type": "expenses",
        },
        {
            "month": "invalid-date",
            "quarter": "invalid-q",
            "property_name": "Building B",
            "tenant_name": "Tech Inc",
            "ledger_description": "Single Language Desc",
            "profit": 150.0,
            "ledger_type": "revenue",
        },
    ]
    return pd.DataFrame(data)


def test_normalize_data_date_parsing(raw_df: pd.DataFrame):
    """Test 'month' strings are correctly cast to datetime 'date'."""
    df = normalize_data(raw_df)
    
    assert "date" in df.columns
    
    # 2025-M01 -> 2025-01-01
    assert df.loc[0, "date"] == pd.Timestamp("2025-01-01")
    
    # 2024-M12 -> 2024-12-01
    assert df.loc[1, "date"] == pd.Timestamp("2024-12-01")
    
    # Invalid dates become NaT
    assert pd.isna(df.loc[2, "date"])


def test_normalize_data_quarter_parsing(raw_df: pd.DataFrame):
    """Test 'quarter' strings are correctly cast to datetime 'quarter_start'."""
    df = normalize_data(raw_df)
    
    assert "quarter_start" in df.columns
    
    # 2025-Q1 -> 2025-01-01
    assert df.loc[0, "quarter_start"] == pd.Timestamp("2025-01-01")
    
    # 2024-Q4 -> 2024-10-01
    assert df.loc[1, "quarter_start"] == pd.Timestamp("2024-10-01")
    
    # Invalid quarters become NaT
    assert pd.isna(df.loc[2, "quarter_start"])


def test_normalize_data_string_stripping(raw_df: pd.DataFrame):
    """Test whitespace is stripped from categorical string columns."""
    df = normalize_data(raw_df)
    
    assert df.loc[0, "property_name"] == "Building A"
    assert df.loc[1, "tenant_name"] == "Acme Corp"
    
    # ledger_description should NOT be stripped generally (per the logic, handled later)
    assert df.loc[0, "ledger_description"] == "Loyer de base | Base Rent"


def test_normalize_data_missing_fills(raw_df: pd.DataFrame):
    """Test missing core entities are filled with defaults."""
    df = normalize_data(raw_df)
    
    # Building A had missing tenant
    assert df.loc[0, "tenant_name"] == "N/A"
    
    # Row 1 had missing property_name -> Should become Corporate/General
    assert df.loc[1, "property_name"] == OVERHEAD_PROPERTY


def test_normalize_data_bilingual_description_extraction(raw_df: pd.DataFrame):
    """Test the English part of the description is correctly extracted."""
    df = normalize_data(raw_df)
    
    assert "description_en" in df.columns
    
    # "Loyer de base | Base Rent" -> "Base Rent"
    assert df.loc[0, "description_en"] == "Base Rent"
    
    # "Taxes | Property Taxes" -> "Property Taxes"
    assert df.loc[1, "description_en"] == "Property Taxes"
    
    # "Single Language Desc" -> "Single Language Desc" (no pipe)
    assert df.loc[2, "description_en"] == "Single Language Desc"


def test_normalize_data_time_hierarchy(raw_df: pd.DataFrame):
    """Test derived year and month_val columns are created from dates."""
    df = normalize_data(raw_df)
    
    assert "year" in df.columns
    assert "month_val" in df.columns
    
    assert df.loc[0, "year"] == 2025
    assert df.loc[0, "month_val"] == 1
    
    assert df.loc[1, "year"] == 2024
    assert df.loc[1, "month_val"] == 12
    
    # NaT rows should have NaN for derived year/month
    assert pd.isna(df.loc[2, "year"])
    assert pd.isna(df.loc[2, "month_val"])
