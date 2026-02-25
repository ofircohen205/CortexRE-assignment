"""
frontend/common.py
==================
Shared resources and utilities for the Streamlit frontend.

The chat tab communicates with the FastAPI backend over HTTP (no direct
graph import needed there).  The EDA tab still reads the local dataframe
directly for fast, interactive visualisations.
"""

from __future__ import annotations

import glob
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Make src/ importable when running `streamlit run src/frontend/app.py`
_SRC  = Path(__file__).resolve().parent.parent
_ROOT = _SRC.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.services.portfolio.normalization import normalize_data  # noqa: E402


@st.cache_resource(show_spinner="Loading dataset …")
def load_dataframe() -> pd.DataFrame:
    """
    Load and normalise the parquet dataset once per Streamlit session.
    Used only by the EDA tab — the chat tab talks to the FastAPI backend.
    """
    parquet_files = glob.glob(str(_ROOT / "data" / "*.parquet"))
    if not parquet_files:
        st.error("No parquet file found in `data/`. Please add the dataset and restart.")
        st.stop()

    return normalize_data(pd.read_parquet(parquet_files[0]))
