"""Unit tests for critique_agent_node."""

from unittest.mock import MagicMock
from src.agents.nodes.critique_agent import critique_agent_node
from src.services.llm.service import CritiqueResult
from src.core.config import settings


def _make_state(revision_count=0, steps=None, draft="The answer is 100,000.00."):
    mock_llm = MagicMock()
    mock_llm.critique_response.return_value = CritiqueResult(
        approved=False,
        issues=["Contains currency symbol '$'."],
        revised_answer="The answer is 100,000.00.",
    )
    return {
        "query": "What is the revenue?",
        "draft_answer": draft,
        "tool_log": [],
        "revision_count": revision_count,
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
    mock_llm.critique_response.return_value = CritiqueResult(
        approved=False,
        issues=["Contains currency symbol '$'."],
        revised_answer="The revenue is 500,000.00.",
        formatting_only=True,
    )
    state = {
        "query": "What is the revenue?",
        "draft_answer": "The revenue is $500,000.00.",
        "tool_log": [],
        "revision_count": 0,
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
    mock_llm.critique_response.return_value = CritiqueResult(
        approved=False,
        issues=["Contains currency symbol '$'."],
        revised_answer=None,
        formatting_only=True,
    )
    state = {
        "query": "What is the revenue?",
        "draft_answer": "The revenue is $500,000.00.",
        "tool_log": [],
        "revision_count": 0,
        "steps": [],
        "_llm": mock_llm,
    }
    result = critique_agent_node(state)

    # Falls through to normal rejection loop
    assert result.get("critique") is not None


def test_non_formatting_issue_loops_to_research():
    """When formatting_only=False, critique should loop back to research agent."""
    mock_llm = MagicMock()
    mock_llm.critique_response.return_value = CritiqueResult(
        approved=False,
        issues=["Revenue figure 500,000 does not match tool result of 400,000."],
        revised_answer="The revenue is 400,000.00.",
        formatting_only=False,
    )
    state = {
        "query": "What is the revenue?",
        "draft_answer": "The revenue is 500,000.00.",
        "tool_log": [],
        "revision_count": 0,
        "steps": [],
        "_llm": mock_llm,
    }
    result = critique_agent_node(state)

    assert result.get("critique") is not None, "factual issue must trigger research loop"
