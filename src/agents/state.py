"""
agents/state.py
===============
Defines the shared state schema for the LangGraph multi-agent graph.

Every node receives the *full* state and returns a partial dict of fields
it wants to update.  LangGraph merges the returned dict into the previous
state to produce the next state — nodes never mutate the object in-place.
"""

from __future__ import annotations

from typing import Any, Annotated
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """
    The single, shared context object passed through every node in the graph.

    Fields are optional (``total=False``) so each node only needs to declare
    the keys it produces; LangGraph merges partial updates automatically.
    """

    # ---- Input ----
    query: str
    """The raw natural-language question from the user."""

    messages: Annotated[list[BaseMessage], add_messages]
    """
    The full conversation history, managed by LangGraph.
    New messages are appended to this list automatically via the `add_messages` reducer.
    """

    # ---- Input Guard outputs ----
    blocked: bool
    """True when the input guard rejects the query (off-topic, injection, etc.)."""

    block_reason: str | None
    """Human-readable explanation of why the query was blocked."""

    # ---- Research Agent outputs ----
    draft_answer: str | None
    """
    The unreviewed answer produced by the research agent after tool calls.
    Passed to the critique agent for review.
    """

    tool_log: list[dict[str, Any]]
    """
    Structured log of every tool invocation during the research phase.
    Each entry has ``tool_name``, ``args``, and ``result``.
    Passed to the critique agent so it can verify figures.
    """

    # ---- Critique Agent outputs ----
    critique: str | None
    """
    Structured feedback from the critique agent when the draft is rejected.
    Re-injected into the research agent prompt on the next revision cycle.
    """

    revision_count: int
    """Number of research→critique revision cycles completed (max = MAX_REVISIONS)."""

    draft_history: list[dict[str, Any]]
    """
    History of every scored draft produced during revision cycles.
    Each entry: {"draft": str, "weighted_total": int, "scores": dict[str, int]}
    Used by the critique agent to select the best answer when the revision cap is reached.
    """

    # ---- Output Guard outputs ----
    final_answer: str | None
    """
    The fully validated, sanitised answer produced by the output guard.
    This is the only field the API / UI layer reads.
    """

    steps: list[dict[str, Any]]
    """
    Ordered list of process steps for observability.
    Each step: {"node": str, "type": str, "message": str, "data": dict | None}
    """

    # ---- Internal context (injected by _inject_context, not persisted) ----
    _df: Any
    """The normalised portfolio DataFrame — injected at runtime, never stored."""

    _tools: dict[str, Any]
    """Tool name → BaseTool mapping — injected at runtime, never stored."""

    _llm: Any
    """LLMService instance — injected at runtime, never stored."""
