"""
frontend/chat_ui.py
===================
Chat interface components for the Streamlit frontend.

Communicates with the FastAPI backend via HTTP instead of calling the
LangGraph directly, so the Streamlit process is a pure thin client.
"""

from __future__ import annotations

import os
import uuid

import time

import requests
import streamlit as st
from loguru import logger

# ---------------------------------------------------------------------------
# Backend configuration
# ---------------------------------------------------------------------------

_API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
_QUERY_URL = f"{_API_BASE}/query"
_TIMEOUT   = int(os.getenv("API_TIMEOUT_SECONDS", "60"))


def _post_query(query: str, thread_id: str | None = None) -> dict:
    """
    POST ``{"query": query}`` to the FastAPI backend and return the
    parsed JSON response dict.

    Raises:
        requests.HTTPError  – non-2xx response from the backend.
        requests.ConnectionError – backend is unreachable.
        requests.Timeout    – backend took longer than ``_TIMEOUT`` seconds.
    """
    logger.info("Sending query to API | url={} query={!r}", _QUERY_URL, query)
    resp = requests.post(
        _QUERY_URL,
        json={"query": query, "thread_id": thread_id},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    logger.info(
        "API response received | intent={} entities={}",
        data.get("intent"),
        data.get("entities"),
    )
    return data


def _stream_text(text: str):
    """Yield words from text with a small delay to simulate streaming."""
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.05)


# ---------------------------------------------------------------------------
# Streamlit component
# ---------------------------------------------------------------------------

def render_chat_tab():
    """Render the Agent Chat tab."""
    
    # --- Session State Initialization ---
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    
    if "thread_id" not in st.session_state:
        st.session_state["thread_id"] = str(uuid.uuid4())

    st.subheader("Asset Management Assistant")
    
    # --- Custom CSS ---
    st.markdown("""
        <style>
        [data-testid="stSidebar"] {
            background-color: #000000;
        }
        .stButton>button {
            border-radius: 8px;
        }
        </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.title("Session")
        
        if st.sidebar.button("New Chat", use_container_width=True, type="primary"):
            st.session_state["messages"] = []
            st.session_state["thread_id"] = str(uuid.uuid4())
            st.rerun()
            
        st.sidebar.divider()
        st.sidebar.caption(f"ID: `{st.session_state['thread_id'][:8]}...`")
    
    # Suggested queries
    with st.expander("Sample queries", expanded=False):
        examples = [
            "What is the P&L for all properties in 2024?",
            "Compare all properties by NOI",
            "Which property had the highest OER in 2025?",
            "Show the top expense drivers across the portfolio",
            "How did NOI grow from 2024 to 2025?",
        ]
        cols = st.columns(2)
        for i, ex in enumerate(examples):
            if cols[i % 2].button(ex, key=f"btn_{i}"):
                st.session_state["prefill"] = ex

    # ---------------------------------------------------------------------------
    # API connectivity banner
    # ---------------------------------------------------------------------------
    try:
        health = requests.get(f"{_API_BASE}/health", timeout=3)
        if health.status_code != 200:
            st.warning(
                f"Backend returned status {health.status_code}. "
                "Queries may fail."
            )
    except requests.ConnectionError:
        st.error(
            f"Cannot reach the backend at **{_API_BASE}**. "
            "Start the FastAPI server (`make run`) and refresh this page."
        )
        return

    # ---------------------------------------------------------------------------
    # Chat history and response container
    # ---------------------------------------------------------------------------
    chat_container = st.container()

    with chat_container:
        for msg in st.session_state["messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # ---------------------------------------------------------------------------
    # Input
    # ---------------------------------------------------------------------------
    prefill = st.session_state.pop("prefill", "")
    user_input = st.chat_input("Ask about your real-estate portfolio …")
    query = user_input or prefill

    if query:
        # 1. User message
        st.session_state["messages"].append({"role": "user", "content": query})

        with chat_container:
            with st.chat_message("user"):
                st.markdown(query)

        # 2. Assistant response
        with chat_container:
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    answer = None
                    try:
                        data = _post_query(query, thread_id=st.session_state["thread_id"])
                        answer = data.get("answer") or "I could not generate a response."

                    except requests.HTTPError as exc:
                        status = exc.response.status_code if exc.response is not None else "?"
                        try:
                            detail = exc.response.json().get("detail", str(exc))
                        except Exception:
                            detail = str(exc)
                        logger.error("HTTP {} error from backend | query={!r} detail={}", status, query, detail)
                        answer = f"The backend returned an error (HTTP {status}): {detail}"

                    except requests.ConnectionError:
                        logger.error("Connection error – backend unreachable | url={}", _QUERY_URL)
                        answer = f"Could not reach the backend at **{_API_BASE}**. Is the FastAPI server running?"

                    except requests.Timeout:
                        logger.error("Request timeout | query={!r}", query)
                        answer = "The request timed out. Please try a simpler query."

                    except Exception as exc:
                        logger.exception("Unexpected error | query={!r}: {}", query, exc)
                        answer = f"An unexpected error occurred: {exc}"

                if answer:
                    answer = answer.replace("$", "\\$")
                    st.write_stream(_stream_text(answer))

        st.session_state["messages"].append({"role": "assistant", "content": answer})
