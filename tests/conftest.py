import pytest
import pandas as pd
from src.services.portfolio.asset_manager import AssetManagerAssistant

@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Mock DataFrame for testing portfolio queries."""
    data = [
        {"property_name": "Building A", "year": 2024, "ledger_type": "revenue",
         "profit": 100.0, "tenant_name": "Tenant 1", "ledger_category": "revenue_rent_taxed",
         "ledger_group": "rental_income"},
        {"property_name": "Building A", "year": 2024, "ledger_type": "expenses",
         "profit": -40.0, "tenant_name": None, "ledger_category": "bank_charges",
         "ledger_group": "general_expenses"},
        {"property_name": "Building A", "year": 2025, "ledger_type": "revenue",
         "profit": 120.0, "tenant_name": "Tenant 1", "ledger_category": "revenue_rent_taxed",
         "ledger_group": "rental_income"},
        {"property_name": "Building A", "year": 2025, "ledger_type": "expenses",
         "profit": -50.0, "tenant_name": None, "ledger_category": "insurance_in_general",
         "ledger_group": "taxes_and_insurances"},
        {"property_name": "Building B", "year": 2024, "ledger_type": "revenue",
         "profit": 200.0, "tenant_name": "Tenant 2", "ledger_category": "revenue_rent_taxed",
         "ledger_group": "rental_income"},
        {"property_name": "Building B", "year": 2024, "ledger_type": "expenses",
         "profit": -90.0, "tenant_name": None, "ledger_category": "real_estate_taxes",
         "ledger_group": "taxes_and_insurances"},
    ]
    return pd.DataFrame(data)


@pytest.fixture
def am(sample_df) -> AssetManagerAssistant:
    return AssetManagerAssistant(sample_df)
