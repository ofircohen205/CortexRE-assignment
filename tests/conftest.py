import pytest
import pandas as pd
from src.services.portfolio.asset_manager import AssetManagerAssistant

@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Mock DataFrame for testing portfolio queries."""
    data = [
        {"property_name": "Building A", "year": 2024, "ledger_type": "revenue", "profit": 100.0},
        {"property_name": "Building A", "year": 2024, "ledger_type": "expenses", "profit": -40.0},
        {"property_name": "Building A", "year": 2025, "ledger_type": "revenue", "profit": 120.0},
        {"property_name": "Building A", "year": 2025, "ledger_type": "expenses", "profit": -50.0},
        {"property_name": "Building B", "year": 2024, "ledger_type": "revenue", "profit": 200.0},
        {"property_name": "Building B", "year": 2024, "ledger_type": "expenses", "profit": -90.0},
    ]
    return pd.DataFrame(data)


@pytest.fixture
def am(sample_df) -> AssetManagerAssistant:
    return AssetManagerAssistant(sample_df)
