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
