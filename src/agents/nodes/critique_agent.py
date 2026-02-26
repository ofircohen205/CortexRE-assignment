"""
agents/nodes/critique_agent.py
================================
Node 3 — Critique Agent.

Reviews the research agent's draft answer against the original question and
the tool call log. Scores it on four weighted dimensions (accuracy, completeness,
clarity, format) for a weighted total out of 100. Approves drafts that reach
CRITIQUE_SCORE_THRESHOLD; rejects others and loops back to the research agent.

At the revision cap, the draft with the highest weighted_total across all
revision cycles is accepted.
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
    - ``{"critique": None}`` (draft approved — propagates to output guard), or
    - ``{"critique": "<feedback>", "revision_count": n, "draft_history": [...]}``
      for a research retry, or
    - ``{"draft_answer": "<best>", "critique": None}`` when the revision cap
      is reached (best draft selected by weighted_total).
    """
    query: str = state.get("query", "")
    draft_answer: str = state.get("draft_answer", "")
    tool_log: list[dict] = state.get("tool_log", [])
    revision_count: int = state.get("revision_count", 0)
    draft_history: list[dict[str, Any]] = list(state.get("draft_history", []))
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
        logger.info(
            "CritiqueAgent: Draft approved | weighted_total={}/100",
            result.weighted_total,
        )
        steps.append({
            "node": "CritiqueAgent",
            "type": "info",
            "message": f"Draft approved (score {result.weighted_total}/100)",
            "data": {"scores": result.scores, "weighted_total": result.weighted_total, "issues": []},
        })
        return {"critique": None, "steps": steps}

    new_revision_count = revision_count + 1

    # Formatting-only bypass: apply revised_answer directly, skip research loop
    if result.formatting_only and result.revised_answer:
        logger.info(
            "CritiqueAgent: Formatting-only issues — applying revision directly "
            "(score {}/100)", result.weighted_total,
        )
        steps.append({
            "node": "CritiqueAgent",
            "type": "info",
            "message": f"Formatting-only issues — applying revision directly (score {result.weighted_total}/100)",
            "data": {"scores": result.scores, "issues": result.issues},
        })
        return {
            "draft_answer": result.revised_answer,
            "critique": None,
            "revision_count": new_revision_count,
            "steps": steps,
        }

    logger.warning(
        "CritiqueAgent: Draft REJECTED | weighted_total={}/100 issues={} revision={}/{}",
        result.weighted_total,
        len(result.issues),
        new_revision_count,
        settings.MAX_REVISIONS,
    )

    # Append current draft to history before deciding what to do
    draft_history.append({
        "draft": draft_answer,
        "weighted_total": result.weighted_total,
        "scores": result.scores,
    })

    if new_revision_count >= settings.MAX_REVISIONS:
        # Select the draft with the highest weighted_total from all revisions
        best = max(draft_history, key=lambda entry: entry["weighted_total"])
        logger.warning(
            "CritiqueAgent: Revision cap ({}) reached — selecting best draft "
            "(weighted_total={})",
            settings.MAX_REVISIONS,
            best["weighted_total"],
        )
        steps.append({
            "node": "CritiqueAgent",
            "type": "warning",
            "message": (
                f"Revision cap ({settings.MAX_REVISIONS}) reached — "
                f"accepting best-scoring draft ({best['weighted_total']}/100)"
            ),
            "data": {"scores": result.scores, "issues": result.issues},
        })
        return {
            "draft_answer": best["draft"],
            "critique": None,
            "revision_count": new_revision_count,
            "draft_history": draft_history,
            "steps": steps,
        }

    # Build critique feedback with per-dimension scores for the research agent
    score_summary = (
        f"Scores — accuracy: {result.scores.get('accuracy', 0)}/10, "
        f"completeness: {result.scores.get('completeness', 0)}/10, "
        f"clarity: {result.scores.get('clarity', 0)}/10, "
        f"format: {result.scores.get('format', 0)}/10 "
        f"(weighted total: {result.weighted_total}/100)"
    )
    critique_text = (
        f"The previous answer scored {result.weighted_total}/100 and was rejected.\n"
        f"{score_summary}\n\n"
        "Issues:\n"
        + "\n".join(f"- {issue}" for issue in result.issues)
    )
    if result.revised_answer:
        critique_text += f"\n\nSuggested correction: {result.revised_answer}"

    steps.append({
        "node": "CritiqueAgent",
        "type": "warning",
        "message": f"Draft REJECTED (Revision {new_revision_count}, score {result.weighted_total}/100)",
        "data": {
            "scores": result.scores,
            "weighted_total": result.weighted_total,
            "issues": result.issues,
        },
    })

    return {
        "critique": critique_text,
        "revision_count": new_revision_count,
        "draft_history": draft_history,
        "steps": steps,
    }
