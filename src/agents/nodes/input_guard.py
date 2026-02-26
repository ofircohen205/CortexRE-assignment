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


def input_guard_node(state: AgentState) -> dict[str, Any]:
    """
    Node 1 — Input Guard.

    Returns ``blocked=True`` with a ``block_reason`` and a ready-made
    ``final_answer`` when the query should not be processed.  Otherwise
    returns ``blocked=False`` and the graph continues to the research agent.
    """
    query: str = state.get("query", "").strip()
    llm: LLMService = state["_llm"]
    steps: list[dict[str, Any]] = list(state.get("steps", []))

    # ------------------------------------------------------------------
    # Fast-fail: mechanical checks (no LLM call)
    # ------------------------------------------------------------------
    if not query:
        logger.warning("InputGuard: Rejecting empty query before LLM check")
        steps.append({
            "node": "InputGuard",
            "type": "warning",
            "message": "Rejecting empty query",
            "data": {"reason": "empty_query"}
        })
        return {
            "blocked": True,
            "block_reason": "empty_query",
            "final_answer": (
                "Your message appears to be empty. "
                "Please enter a question about your real-estate portfolio."
            ),
            "steps": steps,
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
        steps.append({
            "node": "InputGuard",
            "type": "warning",
            "message": "Query blocked by LLM",
            "data": {"reason": result.reason, "query_snippet": query[:100]}
        })
        return {
            "blocked": True,
            "block_reason": result.reason,
            "final_answer": (
                "I can only help with real-estate asset management questions. "
                "Please ask something related to your portfolio, properties, "
                "financials, or asset performance."
            ),
            "steps": steps,
        }

    logger.debug("InputGuard: Query passed safety checks")
    steps.append({
        "node": "InputGuard",
        "type": "info",
        "message": "Query passed safety checks",
        "data": {"allowed": True}
    })
    return {"blocked": False, "steps": steps}
