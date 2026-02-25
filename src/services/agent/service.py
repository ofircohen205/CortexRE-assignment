"""
services/agent/service.py
==========================
Manages the compiled LangGraph agent and conversational checkpointing.
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.memory import MemorySaver

from src.services.portfolio.service import PortfolioService
from src.services.llm.service import LLMService
from src.services.agent.exceptions import GraphNotInitializedError, AgentInvocationError


class AgentService:
    """
    Manages the LangGraph agent instance and its conversational state.

    Uses a ``MemorySaver`` checkpointer for multi-turn session persistence.
    This can be swapped for ``PostgresSaver`` in a fully scaled environment.
    """

    def __init__(
        self,
        portfolio_service: PortfolioService,
        llm_service: LLMService,
    ) -> None:
        self.portfolio_service = portfolio_service
        self.llm_service = llm_service
        self._graph: CompiledStateGraph | None = None
        self._checkpointer = MemorySaver()

    def initialize(self) -> None:
        """Compile the agent workflow graph with the checkpointer."""
        from src.agents.workflow import build_graph

        logger.info("Initializing AgentService and compiling workflow graph...")
        try:
            self._graph = build_graph(
                self.portfolio_service.df,
                llm_service=self.llm_service,
                checkpointer=self._checkpointer,
            )
            logger.info("AgentService initialized successfully with MemorySaver persistence.")
        except Exception as exc:
            logger.exception("Failed to compile agent workflow graph")
            raise GraphNotInitializedError() from exc

    @property
    def graph(self) -> CompiledStateGraph:
        if self._graph is None:
            raise GraphNotInitializedError()
        return self._graph

    def invoke(self, query: str, thread_id: str) -> dict[str, Any]:
        """Run the agent graph for a specific session thread.

        Args:
            query: The raw natural-language question from the user.
            thread_id: Identifies the conversation session for checkpointing.

        Returns:
            The final ``AgentState`` dict produced by the graph.

        Raises:
            AgentInvocationError: If the graph raises any exception during execution.
        """
        config = {"configurable": {"thread_id": thread_id}}
        logger.info(f"AgentService: Running graph for thread {thread_id!r} | query={query!r}")
        try:
            result = self.graph.invoke({"query": query}, config=config)
            
            # Log high-level outcome without dumping massive state dicts
            blocked = result.get("blocked", False)
            revisions = result.get("revision_count", 0)
            answer_len = len(result.get("final_answer", ""))
            
            logger.info(
                f"AgentService: Graph execution finished | blocked={blocked} "
                f"revisions={revisions} answer_length={answer_len}"
            )
            return result
        except Exception as exc:
            logger.exception("AgentService: Error during agent invocation for thread {}", thread_id)
            raise AgentInvocationError(str(exc)) from exc
