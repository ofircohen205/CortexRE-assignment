"""
services/portfolio/asset_manager.py
=====================================
Core financial calculation layer for the CortexRE portfolio dataset.

All methods perform pure pandas operations against the normalised DataFrame
stored in ``self.df``.  No data is mutated in-place.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.services.portfolio.normalization import OVERHEAD_PROPERTY


class AssetManagerAssistant:
    """Wraps a normalised portfolio DataFrame and exposes financial calculations."""

    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df

    def get_property_pl(
        self, property_name: str, year: int | None = None
    ) -> dict[str, Any]:
        """Return P&L summary (revenue, expenses, NOI) for a single property.

        Args:
            property_name: Exact property name as it appears in the dataset.
            year: Optional fiscal year filter.  ``None`` aggregates all years.

        Returns:
            Dict with keys ``revenue``, ``expenses``, and ``noi`` (all floats).
        """
        mask = self.df["property_name"] == property_name
        if year is not None:
            mask &= self.df["year"].astype(int) == year

        subset = self.df[mask]
        summary: dict[str, Any] = subset.groupby("ledger_type")["profit"].sum().to_dict()

        rev = summary.get("revenue", 0)
        exp = summary.get("expenses", 0)
        summary["revenue"] = rev
        summary["expenses"] = exp
        summary["noi"] = rev + exp
        return summary

    def get_portfolio_summary(self, year: int | None = None) -> dict[str, Any]:
        """Aggregate financials across all portfolio properties.

        Corporate/General overhead entries are excluded automatically.

        Args:
            year: Optional fiscal year filter.  ``None`` aggregates all years.

        Returns:
            Dict with keys ``revenue``, ``expenses``, and ``noi`` (all floats).
        """
        mask = self.df["property_name"] != OVERHEAD_PROPERTY
        if year is not None:
            mask &= self.df["year"].astype(int) == year

        subset = self.df[mask]
        summary: dict[str, Any] = subset.groupby("ledger_type")["profit"].sum().to_dict()
        summary["noi"] = summary.get("revenue", 0) + summary.get("expenses", 0)
        return summary

    def calculate_oer(self, property_name: str, year: int) -> float:
        """Calculate the Operating Expense Ratio (|expenses| / revenue).

        A higher OER indicates a larger share of revenue consumed by operating
        costs, which is generally unfavourable.

        Args:
            property_name: Exact property name as it appears in the dataset.
            year: The fiscal year to calculate OER for.

        Returns:
            OER as a float (e.g. ``0.35`` = 35 %).  Returns 0.0 when there is
            no revenue for the requested combination.
        """
        pl = self.get_property_pl(property_name, year)
        rev = pl.get("revenue", 0)
        exp = pl.get("expenses", 0)
        if rev == 0:
            return 0.0
        return abs(exp) / rev

    def get_growth_metrics(self, metric: str = "noi") -> dict[str, dict[str, float]]:
        """Calculate year-over-year growth for each property.

        Args:
            metric: One of ``"noi"``, ``"revenue"``, or ``"expenses"``.

        Returns:
            A nested dict ``{property_name: {"{yr_prev}\u2192{yr_curr}": growth_ratio}}``
            covering every consecutive year pair in the dataset.
            Returns an empty dict when fewer than two years of data are available.
        """
        available_years = sorted(self.df["year"].dropna().astype(int).unique())
        if len(available_years) < 2:  # noqa: PLR2004
            return {}

        year_pairs = list(zip(available_years, available_years[1:]))
        properties = [
            p for p in self.df["property_name"].unique() if p != OVERHEAD_PROPERTY
        ]

        results: dict[str, dict[str, float]] = {}
        for prop in properties:
            prop_growth: dict[str, float] = {}
            for yr_prev, yr_curr in year_pairs:
                val_prev = self.get_property_pl(prop, yr_prev).get(metric, 0)
                val_curr = self.get_property_pl(prop, yr_curr).get(metric, 0)
                label = f"{yr_prev}\u2192{yr_curr}"
                prop_growth[label] = (val_curr - val_prev) / abs(val_prev) if val_prev else 0.0
            results[prop] = prop_growth

        return results

    def compare_properties(self, field: str = "noi") -> pd.Series:
        """Rank all properties from highest to lowest by a financial metric.

        ``field`` is a *derived* metric — revenue and expenses are stored as
        rows distinguished by ``ledger_type``, so the data is pivoted first
        and NOI is computed as revenue + expenses.

        Args:
            field: One of ``"noi"`` (default), ``"revenue"``, or ``"expenses"``.

        Returns:
            A ``pd.Series`` mapping property name → metric value, sorted
            descending.

        Raises:
            KeyError: If *field* is not a recognised metric.
        """
        pivot = (
            self.df[self.df["property_name"] != OVERHEAD_PROPERTY]   # exclude Corporate/General overhead
            .groupby(["property_name", "ledger_type"])["profit"]
            .sum()
            .unstack(fill_value=0)
        )
        for col in ("revenue", "expenses"):
            if col not in pivot.columns:
                pivot[col] = 0.0
        pivot["noi"] = pivot["revenue"] + pivot["expenses"]

        metric = field.lower()
        if metric not in pivot.columns:
            raise KeyError(
                f"Unknown metric '{field}'. Valid options: noi, revenue, expenses."
            )
        return pivot[metric].sort_values(ascending=False)

    def top_expense_drivers(
        self, property_name: str | None = None
    ) -> pd.Series:
        """Identify the largest expense categories by total cost.

        Args:
            property_name: Optional property to scope the analysis to.
                           When ``None``, the entire portfolio is analysed.

        Returns:
            A ``pd.Series`` mapping ledger category → summed expense value
            (negative numbers), sorted ascending (most negative / largest
            expense first).
        """
        mask = self.df["ledger_type"] == "expenses"
        if property_name is not None:
            mask &= self.df["property_name"] == property_name
        return self.df[mask].groupby("ledger_category")["profit"].sum().sort_values()

    def query_portfolio(
        self,
        dimensions: list[str],
        metrics: list[str] = ["profit"],
        filters: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Flexible query engine for custom portfolio analysis.

        Allows grouping by specific dimensions, applying basic equality filters,
        and aggregating numerical metrics. This provides safe, dynamic querying
        without executing arbitrary code.

        Args:
            dimensions: Columns to group by (e.g., ``["year"]``, ``["property_name", "ledger_type"]``).
            metrics: Numerical columns to sum (default is ``["profit"]``).
            filters: List of dictionaries to filter the data. Each dict should have
                     ``column``, ``operator`` (currently only "==" is supported), and ``value``.

        Returns:
            A list of dictionaries representing the aggregated rows.
        """
        df_view = self.df

        # Apply filters
        if filters:
            for f in filters:
                col = f.get("column")
                val = f.get("value")
                if col in df_view.columns:
                    df_view = df_view[df_view[col] == val]

        # Ensure dimensions exist
        valid_dims = [d for d in dimensions if d in df_view.columns]
        valid_metrics = [m for m in metrics if m in df_view.columns]

        if not valid_dims:
            # If no dimensions, just sum the metrics for the whole view
            if not valid_metrics:
                return []
            agg = df_view[valid_metrics].sum().to_dict()
            return [agg]

        if not valid_metrics:
            return []

        # Group and aggregate
        grouped = df_view.groupby(valid_dims)[valid_metrics].sum().reset_index()

        # Convert to list of dicts for JSON serialization
        return grouped.to_dict(orient="records")
