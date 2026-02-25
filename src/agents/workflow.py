"""
agents/workflow.py
==================
Assembles and compiles the LangGraph ``StateGraph`` for the CortexRE
multi-agent real-estate assistant.

Graph topology
--------------

  START
    │
    ▼
  Input Guard  ──── LLM: topic relevance + injection check
    │                    │
    │ (valid)       (blocked)
    ▼                    ▼
  Research Agent        END
    │
    ▼ (tool loop: list_properties, get_property_pl, …)
  Critique Agent ──── LLM: accuracy + hallucination check
    │                    │
    │ (approved)    (rejected, revision_count < MAX)
    ▼                    │
  Output Guard ◄─────────┘  (after MAX revisions, accepts best answer)
    │
    ▼
  END

All LLM interactions are delegated to ``LLMService`` — this module contains
no direct OpenAI / LangChain calls.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from langgraph.graph import END, StateGraph

from src.agents.state import AgentState
from src.agents.tools.pandas_tools import create_tools
from src.services.llm.service import LLMService
from src.agents.nodes.input_guard import input_guard_node
from src.agents.nodes.research_agent import research_agent_node
from src.agents.nodes.critique_agent import critique_agent_node, MAX_REVISIONS
from src.agents.nodes.output_guard import output_guard_node


# ===========================================================================
# Routing functions
# ===========================================================================

def route_after_input_guard(state: AgentState) -> str:
    """Route to END (blocked) or research_agent (valid)."""
    if state.get("blocked"):
        return END
    return "research_agent"


def route_after_critique(state: AgentState) -> str:
    """
    Route back to research_agent for a revision, or forward to output_guard
    when the draft is approved or the revision cap is reached.
    """
    critique = state.get("critique")
    revision_count = state.get("revision_count", 0)

    if critique and revision_count < MAX_REVISIONS:
        return "research_agent"
    return "output_guard"


# ===========================================================================
# Graph builder
# ===========================================================================

def build_graph(
    df: pd.DataFrame,
    llm_service: LLMService,
    checkpointer: Any | None = None,
) -> Any:
    """
    Build and compile the LangGraph ``StateGraph``.

    Args:
        df: The normalized property dataset.
        llm_service: The shared ``LLMService`` instance for all LLM calls.
        checkpointer: Optional LangGraph checkpointer (e.g. MemorySaver,
                     PostgresSaver) used for conversational persistence.
                     NOTE: do NOT pass a checkpointer to any inner subgraph
                     (e.g. create_react_agent) — only the outer graph needs it.
    """
    tools_list = create_tools(df)
    tools_by_name: dict[str, Any] = {t.name: t for t in tools_list}

    def _inject_context(node_fn):
        """Inject ``_df``, ``_tools``, and ``_llm`` into the state before each node runs."""
        def wrapped(state: AgentState) -> dict[str, Any]:
            return node_fn({**state, "_df": df, "_tools": tools_by_name, "_llm": llm_service})
        wrapped.__name__ = node_fn.__name__
        return wrapped

    graph = StateGraph(AgentState)

    graph.add_node("input_guard",    _inject_context(input_guard_node))
    graph.add_node("research_agent", _inject_context(research_agent_node))
    graph.add_node("critique_agent", _inject_context(critique_agent_node))
    graph.add_node("output_guard",   _inject_context(output_guard_node))

    graph.set_entry_point("input_guard")
    graph.add_conditional_edges(
        "input_guard",
        route_after_input_guard,
        {END: END, "research_agent": "research_agent"},
    )
    graph.add_edge("research_agent", "critique_agent")
    graph.add_conditional_edges(
        "critique_agent",
        route_after_critique,
        {"research_agent": "research_agent", "output_guard": "output_guard"},
    )
    graph.add_edge("output_guard", END)

    return graph.compile(checkpointer=checkpointer)
