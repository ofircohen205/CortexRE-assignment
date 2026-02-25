"""
evaluation/ground_truth.py
===========================
Programmatic generation of the ground truth dataset used by TruLens evaluation.

Calculates expected values directly from the normalized dataframe so the test
cases are always consistent with the actual data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from loguru import logger

from src.core.config import settings
from src.services.portfolio.asset_manager import AssetManagerAssistant
from src.services.portfolio.normalization import OVERHEAD_PROPERTY, normalize_data


def generate_ground_truth(output_path: Path, max_properties: int | None = None) -> list[dict]:
    """
    Generate ground truth test cases and write them to *output_path*.

    Creates the parent directory if it does not exist.

    Args:
        output_path: Where to write the ``ground_truth.json`` file.
        max_properties: If set, limits the number of properties included in
                        P&L test cases. Defaults to all available properties.

    Returns:
        The list of generated test-case dicts (also written to disk).
    """
    logger.info("Generating ground truth from data at {}", settings.DATA_PATH)

    raw_df = pd.read_parquet(settings.DATA_PATH)
    df = normalize_data(raw_df)

    if "date" in df.columns and "year" not in df.columns:
        df["year"] = df["date"].dt.year

    assistant = AssetManagerAssistant(df)

    # Derive all available properties from the data, excluding overhead entries
    properties = sorted(
        p for p in df["property_name"].unique() if p != OVERHEAD_PROPERTY
    )
    if max_properties is not None:
        properties = properties[:max_properties]

    # Derive all available years from the data
    years = sorted(df["year"].dropna().astype(int).unique().tolist())
    ground_truth = []

    # P&L queries — all property × year combinations
    for prop in properties:
        for year in years:
            pl = assistant.get_property_pl(prop, year)
            ground_truth.append({
                "query": f"What was the revenue and NOI for {prop} in {year}?",
                "expected_intent": "pl_analysis",
                "expected_entities": {"property_names": [prop], "year": year},
                "expected_values": {
                    "revenue": float(pl["revenue"]),
                    "noi": float(pl["noi"]),
                },
            })

    # Price comparison
    top_prop = assistant.compare_properties("noi").index[0]
    ground_truth.append({
        "query": "Which property has the highest NOI?",
        "expected_intent": "price_comparison",
        "expected_entities": {"metric": "noi"},
        "expected_values": {"top_property": top_prop},
    })

    # Portfolio summary
    port_2024 = assistant.get_portfolio_summary(2024)
    ground_truth.append({
        "query": "Give me the portfolio total revenue for 2024",
        "expected_intent": "portfolio_summary",
        "expected_entities": {"year": 2024},
        "expected_values": {"revenue": float(port_2024["revenue"])},
    })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(ground_truth, f, indent=2)

    logger.info("Generated {} test cases → {}", len(ground_truth), output_path)
    return ground_truth


def load_or_generate(gt_path: Path) -> list[dict]:
    """
    Return the ground truth dataset, generating it first if the file is absent.

    Args:
        gt_path: Expected path to ``ground_truth.json``.

    Returns:
        The list of test-case dicts.
    """
    if gt_path.exists():
        logger.info("Loading existing ground truth from {}", gt_path)
        with open(gt_path) as fh:
            return json.load(fh)

    logger.info("Ground truth not found — generating now...")
    return generate_ground_truth(gt_path)
