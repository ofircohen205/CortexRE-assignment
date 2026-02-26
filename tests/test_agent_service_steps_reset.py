"""Verify that AgentService always resets steps to [] on each invoke."""

from unittest.mock import MagicMock


def test_invoke_resets_steps_each_turn():
    """graph.invoke() must receive steps=[] so previous turns don't bleed through."""
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "final_answer": "ok",
        "blocked": False,
        "steps": [],
    }

    from src.services.agent.service import AgentService

    svc = AgentService.__new__(AgentService)
    svc._graph = mock_graph

    svc.invoke("what is the revenue?", thread_id="t1")

    call_args = mock_graph.invoke.call_args
    input_dict = call_args[0][0]
    assert "steps" in input_dict, "steps must be explicitly reset each turn"
    assert input_dict["steps"] == [], "steps must be reset to empty list"
