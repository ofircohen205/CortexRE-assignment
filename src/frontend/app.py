"""
frontend/app.py
===============
Main entry point for the CortexRE Streamlit frontend.

Architecture:
- Chat tab  → thin HTTP client calling the FastAPI backend (/query)
- EDA tab   → reads the local parquet file directly (no network needed)
"""

from __future__ import annotations

import streamlit as st

from src.frontend.common import load_dataframe
from src.frontend.chat_ui import render_chat_tab
from src.frontend.eda_ui import render_eda_tab

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="CortexRE Asset Manager",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Load data (EDA tab only — chat tab talks to the backend over HTTP)
# ---------------------------------------------------------------------------

df = load_dataframe()

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.title("CortexRE Asset Management")

tab_chat, tab_eda = st.tabs(["Agent Chat", "Portfolio EDA"])

with tab_chat:
    render_chat_tab()          # no graph arg — calls FastAPI backend

with tab_eda:
    render_eda_tab(df)
