"""Unit tests for critique_agent_node."""

from unittest.mock import MagicMock
from src.agents.nodes.critique_agent import critique_agent_node
from src.services.llm.service import CritiqueResult
from src.core.config import settings


def _low_score_result(issues=None, revised_answer="The answer is 100,000.00.", formatting_only=False):
    """weighted_total=50 → approved=False (below threshold of 80)."""
    return CritiqueResult(
        scores={"accuracy": 5, "completeness": 5, "clarity": 5, "format": 5},
        weighted_total=50,
        issues=issues or ["Contains currency symbol '$'."],
        revised_answer=revised_answer,
        formatting_only=formatting_only,
    )


def _high_score_result():
    """weighted_total=90 → approved=True."""
    return CritiqueResult(
        scores={"accuracy": 10, "completeness": 9, "clarity": 9, "format": 10},
        weighted_total=90,
        issues=[],
        revised_answer=None,
    )


def _make_state(revision_count=0, steps=None, draft="The answer is 100,000.00.", draft_history=None):
    mock_llm = MagicMock()
    mock_llm.critique_response.return_value = _low_score_result()
    return {
        "query": "What is the revenue?",
        "draft_answer": draft,
        "tool_log": [],
        "revision_count": revision_count,
        "draft_history": draft_history or [],
        "steps": steps or [],
        "_llm": mock_llm,
    }


def test_cap_reached_returns_steps():
    """When revision cap is hit, steps must be included in the returned dict."""
    state = _make_state(
        revision_count=settings.MAX_REVISIONS - 1,
        steps=[{"node": "InputGuard", "type": "info", "message": "ok"}]
    )
    result = critique_agent_node(state)
    assert "steps" in result, "cap-reached path must return steps"
    assert len(result["steps"]) > 0, "steps should not be empty"


def test_formatting_only_bypass_applies_revised_answer():
    """When formatting_only=True, critique_agent should accept revised_answer directly."""
    mock_llm = MagicMock()
    mock_llm.critique_response.return_value = _low_score_result(
        issues=["Contains currency symbol '$'."],
        revised_answer="The revenue is 500,000.00.",
        formatting_only=True,
    )
    state = {
        "query": "What is the revenue?",
        "draft_answer": "The revenue is $500,000.00.",
        "tool_log": [],
        "revision_count": 0,
        "draft_history": [],
        "steps": [],
        "_llm": mock_llm,
    }
    result = critique_agent_node(state)

    assert result["draft_answer"] == "The revenue is 500,000.00."
    assert result["critique"] is None, "formatting bypass must not set critique"
    assert "steps" in result
    assert result.get("revision_count") == 1


def test_formatting_only_bypass_skipped_when_no_revised_answer():
    """If revised_answer is None despite formatting_only, fall through to normal loop."""
    mock_llm = MagicMock()
    mock_llm.critique_response.return_value = _low_score_result(
        revised_answer=None,
        formatting_only=True,
    )
    state = {
        "query": "What is the revenue?",
        "draft_answer": "The revenue is $500,000.00.",
        "tool_log": [],
        "revision_count": 0,
        "draft_history": [],
        "steps": [],
        "_llm": mock_llm,
    }
    result = critique_agent_node(state)
    assert result.get("critique") is not None


def test_non_formatting_issue_loops_to_research():
    """When formatting_only=False, critique should loop back to research agent."""
    mock_llm = MagicMock()
    mock_llm.critique_response.return_value = _low_score_result(
        issues=["Revenue figure 500,000 does not match tool result of 400,000."],
        revised_answer="The revenue is 400,000.00.",
        formatting_only=False,
    )
    state = {
        "query": "What is the revenue?",
        "draft_answer": "The revenue is 500,000.00.",
        "tool_log": [],
        "revision_count": 0,
        "draft_history": [],
        "steps": [],
        "_llm": mock_llm,
    }
    result = critique_agent_node(state)
    assert result.get("critique") is not None, "factual issue must trigger research loop"


def test_draft_history_appended_on_rejection():
    """Each rejection must append the draft + score to draft_history."""
    state = _make_state(revision_count=0)
    result = critique_agent_node(state)
    history = result.get("draft_history", [])
    assert len(history) == 1
    assert history[0]["draft"] == "The answer is 100,000.00."
    assert history[0]["weighted_total"] == 50
    assert "scores" in history[0]


def test_best_answer_selected_from_history_at_cap():
    """At revision cap, the draft with highest weighted_total wins."""
    earlier_history = [
        {"draft": "Old best answer.", "weighted_total": 75, "scores": {"accuracy": 8, "completeness": 8, "clarity": 7, "format": 5}},
    ]
    # The current draft scores lower (50) than the history entry (75)
    state = _make_state(
        revision_count=settings.MAX_REVISIONS - 1,
        draft="Current worse answer.",
        draft_history=earlier_history,
    )
    result = critique_agent_node(state)
    assert result["draft_answer"] == "Old best answer.", "must pick the highest-scoring draft"
    assert result["critique"] is None


def test_best_answer_is_current_when_highest():
    """If current draft has the highest score, it wins over history."""
    earlier_history = [
        {"draft": "Older worse answer.", "weighted_total": 30, "scores": {"accuracy": 3, "completeness": 3, "clarity": 3, "format": 3}},
    ]
    # Current draft scores 50 — higher than history entry (30)
    state = _make_state(
        revision_count=settings.MAX_REVISIONS - 1,
        draft="Current better answer.",
        draft_history=earlier_history,
    )
    result = critique_agent_node(state)
    assert result["draft_answer"] == "Current better answer."


def test_approved_draft_not_added_to_history():
    """An approved draft should NOT be appended to draft_history."""
    mock_llm = MagicMock()
    mock_llm.critique_response.return_value = _high_score_result()
    state = {
        "query": "What is the revenue?",
        "draft_answer": "The revenue is 500,000.00.",
        "tool_log": [],
        "revision_count": 0,
        "draft_history": [],
        "steps": [],
        "_llm": mock_llm,
    }
    result = critique_agent_node(state)
    assert result.get("critique") is None
    # draft_history should not be set (or should remain empty)
    assert result.get("draft_history", []) == []
