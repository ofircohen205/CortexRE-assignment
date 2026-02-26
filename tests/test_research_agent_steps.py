"""Verify research_agent_node populates steps with tool call entries."""

from unittest.mock import MagicMock
from langchain_core.messages import AIMessage


def _make_tool_call_response(tool_name, tool_id="call_1", args=None):
    """Return an AIMessage that requests a single tool call."""
    msg = AIMessage(content="")
    msg.tool_calls = [{"name": tool_name, "args": args or {}, "id": tool_id}]
    return msg


def _make_final_response(text="The answer is 100,000.00."):
    msg = AIMessage(content=text)
    msg.tool_calls = []
    return msg


def test_research_agent_adds_tool_steps():
    """Tool calls made during ReAct loop must appear in steps."""
    from src.agents.nodes.research_agent import research_agent_node

    mock_tool = MagicMock()
    mock_tool.invoke.return_value = {"revenue": 100000}

    mock_model = MagicMock()
    # First call returns a tool call; second call returns the final answer
    mock_model.invoke.side_effect = [
        _make_tool_call_response("get_property_pl", args={"property_name": "Building A"}),
        _make_final_response("The revenue for Building A is 100,000.00."),
    ]

    mock_llm = MagicMock()
    mock_llm.chat_model.bind_tools.return_value.with_retry.return_value = mock_model

    state = {
        "query": "What is the revenue for Building A?",
        "critique": None,
        "messages": [],
        "steps": [],
        "_tools": {"get_property_pl": mock_tool},
        "_llm": mock_llm,
    }

    result = research_agent_node(state)

    assert "steps" in result, "research_agent must return steps"
    tool_steps = [s for s in result["steps"] if s.get("type") == "tool"]
    assert len(tool_steps) == 1, "one tool call should produce one tool step"
    assert tool_steps[0]["message"] == "get_property_pl"
    assert tool_steps[0]["data"]["args"] == {"property_name": "Building A"}
    assert tool_steps[0]["data"]["result"] == {"revenue": 100000}


def test_research_agent_no_tool_calls_returns_steps():
    """When no tools are called, steps list is still returned (preserving prior steps)."""
    from src.agents.nodes.research_agent import research_agent_node

    mock_model = MagicMock()
    mock_model.invoke.return_value = _make_final_response("42.")

    mock_llm = MagicMock()
    mock_llm.chat_model.bind_tools.return_value.with_retry.return_value = mock_model

    state = {
        "query": "What is 6 times 7?",
        "critique": None,
        "messages": [],
        "steps": [{"node": "InputGuard", "type": "info", "message": "ok"}],
        "_tools": {},
        "_llm": mock_llm,
    }

    result = research_agent_node(state)
    assert "steps" in result
    # Pre-existing InputGuard step should be preserved
    info_steps = [s for s in result["steps"] if s.get("node") == "InputGuard"]
    assert len(info_steps) == 1
