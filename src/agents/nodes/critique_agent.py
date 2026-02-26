"""
agents/nodes/critique_agent.py
================================
Node 3 — Critique Agent.

An independent LLM reviewer that examines the research agent's draft answer
against the original question and the tool call log.  It either approves the
draft or rejects it with a corrected answer.

If rejected and ``revision_count < MAX_REVISIONS``, the graph loops back to
the research agent with the critique appended to the state.  Once the
revision cap is reached the critique's own ``revised_answer`` is accepted.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.agents.state import AgentState
from src.services.llm.service import LLMService
from src.core.config import settings


def critique_agent_node(state: AgentState) -> dict[str, Any]:
    """
    Node 3 — Critique Agent.

    Reads ``draft_answer`` and ``tool_log`` from state and returns either:
    - ``{"critique": None}`` (unchanged draft propagates to output guard), or
    - ``{"critique": "<feedback>", "revision_count": n}`` for a research retry,
    - ``{"draft_answer": "<revised>", "critique": None}`` when the cap is reached.
    """
    query: str = state.get("query", "")
    draft_answer: str = state.get("draft_answer", "")
    tool_log: list[dict] = state.get("tool_log", [])
    revision_count: int = state.get("revision_count", 0)
    llm: LLMService = state["_llm"]
    steps: list[dict[str, Any]] = list(state.get("steps", []))

    if not draft_answer:
        logger.warning("Critique agent: no draft answer to review — passing through")
        steps.append({
            "node": "CritiqueAgent",
            "type": "warning",
            "message": "No draft answer to review",
        })
        return {"critique": None, "steps": steps}

    result = llm.critique_response(query, tool_log, draft_answer)

    if result.approved:
        logger.info("CritiqueAgent: Draft approved by critique")
        steps.append({
            "node": "CritiqueAgent",
            "type": "info",
            "message": "Draft approved",
            "data": {"raw_response": str(result), "issues": []}
        })
        return {"critique": None, "steps": steps}

    logger.warning(
        "CritiqueAgent: Draft REJECTED | issues={} revision_count={}/{}",
        len(result.issues),
        revision_count + 1,
        settings.MAX_REVISIONS,
    )

    new_revision_count = revision_count + 1

    if new_revision_count >= settings.MAX_REVISIONS:
        # Revision cap reached — accept the critique's corrected answer (or draft)
        accepted = result.revised_answer or draft_answer
        logger.warning(
            "CritiqueAgent: Revision cap ({}) reached — forcing acceptance of revised answer",
            settings.MAX_REVISIONS,
        )
        steps.append({
            "node": "CritiqueAgent",
            "type": "warning",
            "message": f"Revision cap ({settings.MAX_REVISIONS}) reached — accepting best answer",
            "data": {"issues": result.issues},
        })
        return {
            "draft_answer": accepted,
            "critique": None,
            "revision_count": new_revision_count,
            "steps": steps,
        }

    # Formatting-only bypass: apply revised_answer directly, skip research loop
    if not result.approved and result.formatting_only and result.revised_answer:
        logger.info(
            "CritiqueAgent: Formatting-only issues — applying revision directly (no research loop)"
        )
        steps.append({
            "node": "CritiqueAgent",
            "type": "info",
            "message": "Formatting-only issues — applying revision directly",
            "data": {"issues": result.issues},
        })
        return {
            "draft_answer": result.revised_answer,
            "critique": None,
            "revision_count": new_revision_count,
            "steps": steps,
        }

    # Loop back to research agent with critique feedback
    critique_text = (
        "The previous answer had these issues:\n"
        + "\n".join(f"- {issue}" for issue in result.issues)
    )
    if result.revised_answer:
        critique_text += f"\n\nSuggested correction: {result.revised_answer}"

    steps.append({
        "node": "CritiqueAgent",
        "type": "warning",
        "message": f"Draft REJECTED (Revision {new_revision_count})",
        "data": {
            "issues": result.issues,
            "raw_response": str(result)
        }
    })

    return {
        "critique": critique_text,
        "revision_count": new_revision_count,
        "steps": steps,
    }
