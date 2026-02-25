"""
services/portfolio/service.py
==============================
Data access layer: loads, normalizes, and exposes the portfolio dataset.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from loguru import logger

from .asset_manager import AssetManagerAssistant
from .normalization import normalize_data
from .exceptions import DatasetNotFoundError, DataNormalizationError


class PortfolioService:
    """
    Handles all data-related operations for the property portfolio.

    Encapsulates pandas I/O and normalization, and exposes a clean interface
    for other services (``AgentService``, API endpoints).
    """

    def __init__(self, data_path: str) -> None:
        self._data_path = data_path
        self._df: pd.DataFrame | None = None
        self._assistant: AssetManagerAssistant | None = None

    def initialize(self) -> None:
        """Load and normalize the portfolio dataset from *data_path*."""
        logger.info("Initializing PortfolioService with data from: {}", self._data_path)

        try:
            raw_df = pd.read_parquet(self._data_path)
            logger.debug(f"PortfolioService: Loaded {len(raw_df)} raw rows from parquet")
        except FileNotFoundError:
            logger.error(f"PortfolioService: Dataset not found at {self._data_path}")
            raise DatasetNotFoundError(self._data_path)
        except Exception as exc:
            logger.error(f"PortfolioService: Failed to load parquet: {exc}")
            raise DatasetNotFoundError(self._data_path) from exc

        try:
            self._df = normalize_data(raw_df)
            self._assistant = AssetManagerAssistant(self._df)
            logger.info("PortfolioService initialized with {} rows.", len(self._df))
        except Exception as exc:
            logger.exception("Normalization failed during service initialization")
            raise DataNormalizationError(str(exc)) from exc

    @property
    def df(self) -> pd.DataFrame:
        if self._df is None:
            raise RuntimeError("PortfolioService accessed before initialization.")
        return self._df

    @property
    def property_list(self) -> list[str]:
        """Return a sorted list of all unique property names."""
        if "property_name" not in self.df.columns:
            return []
        return sorted(self.df["property_name"].unique().tolist())

    def get_assistant(self) -> AssetManagerAssistant:
        """Return the ``AssetManagerAssistant`` instance for financial calculations."""
        if self._assistant is None:
            raise RuntimeError("PortfolioService accessed before initialization.")
        return self._assistant

    def get_eda_stats(self) -> dict[str, Any]:
        """Return aggregated statistics for EDA visualization."""
        df = self.df

        # 1. Monthly trends
        monthly_trends = (
            df.groupby(["date", "ledger_type"])["profit"]
            .sum()
            .unstack(fill_value=0)
            .reset_index()
        )
        monthly_trends["noi"] = monthly_trends.get("revenue", 0) + monthly_trends.get("expenses", 0)
        monthly_trends["date"] = monthly_trends["date"].dt.strftime("%Y-%m-%d")

        # 2. Property distribution
        prop_dist = (
            df.groupby("property_name")["profit"]
            .agg(
                total_revenue=lambda x: x[df.loc[x.index, "ledger_type"] == "revenue"].sum(),
                total_expenses=lambda x: x[df.loc[x.index, "ledger_type"] == "expenses"].sum(),
            )
            .reset_index()
        )
        prop_dist["noi"] = prop_dist["total_revenue"] + prop_dist["total_expenses"]

        # 3. Portfolio KPIs
        kpis: dict[str, Any] = {
            "total_properties": len(self.property_list),
            "date_range": [
                df["date"].min().strftime("%Y-%m-%d"),
                df["date"].max().strftime("%Y-%m-%d"),
            ],
            "total_noi": float(prop_dist["noi"].sum()),
        }

        return {
            "monthly_trends": monthly_trends.to_dict(orient="records"),
            "property_performance": prop_dist.to_dict(orient="records"),
            "portfolio_kpis": kpis,
        }
