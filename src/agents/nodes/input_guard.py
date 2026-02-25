"""
agents/nodes/input_guard.py
============================
Node 1 — Input Guard.

An LLM-powered gatekeeper that validates every incoming query before it
reaches the research agent.  Performs a cheap fast-fail for mechanical
errors (empty / overlong queries) and then delegates topic-relevance and
injection-detection to the LLM.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.agents.state import AgentState
from src.services.llm.service import LLMService

# Absolute character limit — no LLM call needed above this
_MAX_QUERY_LENGTH = 500


def input_guard_node(state: AgentState) -> dict[str, Any]:
    """
    Node 1 — Input Guard.

    Returns ``blocked=True`` with a ``block_reason`` and a ready-made
    ``final_answer`` when the query should not be processed.  Otherwise
    returns ``blocked=False`` and the graph continues to the research agent.
    """
    query: str = state.get("query", "").strip()
    llm: LLMService = state["_llm"]

    # ------------------------------------------------------------------
    # Fast-fail: mechanical checks (no LLM call)
    # ------------------------------------------------------------------
    if not query:
        logger.warning("InputGuard: Rejecting empty query before LLM check")
        return {
            "blocked": True,
            "block_reason": "empty_query",
            "final_answer": (
                "Your message appears to be empty. "
                "Please enter a question about your real-estate portfolio."
            ),
        }

    if len(query) > _MAX_QUERY_LENGTH:
        logger.warning("InputGuard: Rejecting query due to length ({} chars > {})", len(query), _MAX_QUERY_LENGTH)
        return {
            "blocked": True,
            "block_reason": "query_too_long",
            "final_answer": (
                f"Your query is too long ({len(query)} characters). "
                f"Please keep questions under {_MAX_QUERY_LENGTH} characters."
            ),
        }

    # ------------------------------------------------------------------
    # LLM check: topic relevance + injection detection
    # ------------------------------------------------------------------
    result = llm.check_input(query)

    if not result.allowed:
        logger.warning(
            "InputGuard: Query blocked by LLM | reason={!r} | query={!r}",
            result.reason,
            query[:100] + ("..." if len(query) > 100 else "")
        )
        return {
            "blocked": True,
            "block_reason": result.reason,
            "final_answer": (
                "I can only help with real-estate asset management questions. "
                "Please ask something related to your portfolio, properties, "
                "financials, or asset performance."
            ),
        }

    logger.debug("InputGuard: Query passed safety checks")
    return {"blocked": False}
