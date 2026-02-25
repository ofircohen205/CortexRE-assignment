"""
services/portfolio/normalization.py
====================================
Normalizes the raw CortexRE parquet dataset into a clean DataFrame.
"""

from __future__ import annotations

import pandas as pd
import numpy as np

#: Property name used for overhead / corporate entries that don't belong to a
#: specific asset. Centralised here so every module imports it rather than
#: repeating the raw string.
OVERHEAD_PROPERTY: str = "Corporate/General"


def normalize_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply standard normalizations to the dataset.

    Steps applied (in order):
    1. Parse ``month`` column → ``date`` (datetime).
    2. Parse ``quarter`` column → ``quarter_start`` (datetime).
    3. Strip leading/trailing whitespace from string columns.
    4. Fill missing ``property_name`` / ``tenant_name``.
    5. Extract the English half of bilingual ``ledger_description`` values.
    6. Derive ``year`` and ``month_val`` from ``date``.
    """
    df = df.copy()

    # 1. Date standardization: "2025-M01" → 2025-01-01
    if "month" in df.columns:
        df["date"] = pd.to_datetime(
            df["month"].str.replace("-M", "-", regex=False),
            format="%Y-%m",
            errors="coerce",
        )

    # 2. Quarter standardization: "2025-Q1" → 2025-01-01 (start of quarter)
    if "quarter" in df.columns:
        _quarter_map = {"Q1": "01-01", "Q2": "04-01", "Q3": "07-01", "Q4": "10-01"}

        def _parse_quarter(q_str: str) -> pd.Timestamp | float:
            try:
                year, q = q_str.split("-")
                return pd.to_datetime(f"{year}-{_quarter_map[q]}")
            except (ValueError, KeyError):
                return np.nan

        df["quarter_start"] = df["quarter"].apply(_parse_quarter)

    # 3. Categorical consistency — strip whitespace from string columns
    string_cols = df.select_dtypes(include=["object"]).columns
    for col in string_cols:
        if col != "ledger_description":  # keep description as-is
            df[col] = df[col].str.strip()

    # 4. Handle missing property / tenant info
    if "property_name" in df.columns:
        df["property_name"] = df["property_name"].fillna(OVERHEAD_PROPERTY)
    if "tenant_name" in df.columns:
        df["tenant_name"] = df["tenant_name"].fillna("N/A")

    # 5. Bilingual description parsing — extract the English part after "|"
    if "ledger_description" in df.columns:

        def _clean_desc(desc: str | float) -> str | float:
            if pd.isna(desc):
                return desc
            if "|" in desc:
                return desc.split("|")[-1].strip()
            return desc

        df["description_en"] = df["ledger_description"].apply(_clean_desc)

    # 6. Time hierarchy
    if "date" in df.columns:
        df["year"] = df["date"].dt.year
        df["month_val"] = df["date"].dt.month

    return df


def _enrich_asset_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add secondary financial metrics (NOI, OER) by pivoting revenue vs expenses.

    This function is not called during the main pipeline; it is available for
    offline EDA / notebook use.
    """
    metrics = (
        df.groupby(["property_name", "date", "ledger_type"])["profit"]
        .sum()
        .unstack(fill_value=0)
        .reset_index()
    )
    metrics = metrics.rename(
        columns={"revenue": "total_revenue", "expenses": "total_expenses"}
    )
    metrics["noi"] = metrics["total_revenue"] + metrics["total_expenses"]
    metrics["oer"] = metrics.apply(
        lambda x: abs(x["total_expenses"]) / x["total_revenue"]
        if x["total_revenue"] > 0
        else 0,
        axis=1,
    )
    return df.merge(
        metrics[["property_name", "date", "total_revenue", "total_expenses", "noi", "oer"]],
        on=["property_name", "date"],
        how="left",
    )
