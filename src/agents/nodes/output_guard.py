"""
agents/nodes/output_guard.py
==============================
Node 4 — Output Guard.

An LLM-powered final validator that checks the approved draft answer for
hallucinated property names, format violations, and completeness before it
is committed to ``final_answer`` and returned to the user.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.agents.state import AgentState
from src.agents.tools.pandas_tools import list_properties
from src.services.llm.service import LLMService

_FALLBACK = (
    "I was unable to generate a reliable answer for your question. "
    "Please try rephrasing or provide more details about the property or metric you are interested in."
)


def output_guard_node(state: AgentState) -> dict[str, Any]:
    """
    Node 4 — Output Guard.

    Validates the draft answer, applies the LLM's corrections if needed,
    and promotes the result to ``final_answer``.
    """
    query: str = state.get("query", "")
    draft: str = state.get("draft_answer", "")
    llm: LLMService = state["_llm"]
    df = state["_df"]

    if not draft:
        logger.warning("OutputGuard: No draft answer provided to guard — returning fallback")
        return {"final_answer": _FALLBACK}

    # Get known property names for hallucination check
    try:
        known_properties: list[str] = list_properties(df)["properties"]
    except Exception as exc:
        logger.warning(f"OutputGuard: Failed to load property list for validation: {exc}")
        known_properties = []

    result = llm.check_output(query, known_properties, draft)

    if result.valid:
        logger.info("OutputGuard: Draft answer validated — no corrections needed")
        return {"final_answer": draft}

    corrected = result.corrected_answer or draft
    logger.warning("OutputGuard: Draft answer failed validation | applying LLM correction")
    return {"final_answer": corrected}
