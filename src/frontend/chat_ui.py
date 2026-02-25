"""
frontend/chat_ui.py
===================
Chat interface components for the Streamlit frontend.

Communicates with the FastAPI backend via HTTP instead of calling the
LangGraph directly, so the Streamlit process is a pure thin client.
"""

from __future__ import annotations

import os

import requests
import streamlit as st
from loguru import logger

# ---------------------------------------------------------------------------
# Backend configuration
# ---------------------------------------------------------------------------

_API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
_QUERY_URL = f"{_API_BASE}/query"
_TIMEOUT   = int(os.getenv("API_TIMEOUT_SECONDS", "60"))


def _post_query(query: str) -> dict:
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
        json={"query": query},
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


# ---------------------------------------------------------------------------
# Streamlit component
# ---------------------------------------------------------------------------

def render_chat_tab():
    """Render the Agent Chat tab.  No graph argument required."""
    st.subheader("Asset Management Assistant")
    
    st.markdown("""
    <style>
    /* User messages: Right-aligned with blue bubble */
    div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        flex-direction: row-reverse;
        text-align: right;
    }
    div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) div[data-testid="stChatMessageContent"] {
        background-color: #0b93f6;
        color: white;
        border-radius: 18px 18px 4px 18px;
        padding: 10px 15px;
        display: inline-block;
        max-width: 85%;
        margin-left: auto;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }
    /* Set markdown text color inside the user bubble to white */
    div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) div[data-testid="stChatMessageContent"] p {
        color: white;
        margin-bottom: 0;
    }

    /* Assistant messages: Left-aligned with gray bubble */
    div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) div[data-testid="stChatMessageContent"] {
        background-color: #f1f0f0;
        color: black;
        border-radius: 18px 18px 18px 4px;
        padding: 10px 15px;
        display: inline-block;
        max-width: 85%;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }
    div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) div[data-testid="stChatMessageContent"] p {
        color: black;
        margin-bottom: 0;
    }
    
    /* Ensure chat input stays properly at the bottom */
    div[data-testid="stChatInput"] {
        padding-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

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
    # Chat history
    # ---------------------------------------------------------------------------
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

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
        st.session_state["messages"].append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                answer  = None

                try:
                    data     = _post_query(query)
                    answer   = data.get("answer") or "I could not generate a response."

                except requests.HTTPError as exc:
                    status = exc.response.status_code if exc.response is not None else "?"
                    try:
                        detail = exc.response.json().get("detail", str(exc))
                    except Exception:
                        detail = str(exc)
                    logger.error(
                        "HTTP {} error from backend | query={!r} detail={}",
                        status, query, detail,
                    )
                    answer       = f"The backend returned an error (HTTP {status}): {detail}"

                except requests.ConnectionError:
                    logger.error(
                        "Connection error – backend unreachable | url={}", _QUERY_URL
                    )
                    answer = (
                        f"Could not reach the backend at **{_API_BASE}**. "
                        "Is the FastAPI server running?"
                    )

                except requests.Timeout:
                    logger.error(
                        "Request timed out after {}s | query={!r}", _TIMEOUT, query
                    )
                    answer = (
                        f"The request timed out after {_TIMEOUT} seconds. "
                        "The query may be too complex — try rephrasing it."
                    )

                except Exception as exc:
                    logger.exception(
                        "Unexpected error calling backend | query={!r}: {}", query, exc
                    )
                    answer = f"An unexpected error occurred: {exc}"

            # Sanitize LLM output: remove $ signs before rendering.
            # Streamlit treats $...$ as LaTeX math mode, which garbles numbers
            # (e.g. "$2,295,528" becomes spaced-out characters).
            if answer:
                answer = answer.replace("$", "\\$")
            st.markdown(answer)

        st.session_state["messages"].append({"role": "assistant", "content": answer})
