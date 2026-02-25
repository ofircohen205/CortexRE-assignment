"""
evaluation/runner.py
=====================
Agent initialization and invocation helpers used by the evaluation scripts.

Keeps the service bootstrap logic (identical to ``main.py`` lifespan) in one
place so it does not need to be repeated across evaluation entry points.
"""

from __future__ import annotations

from src.core.config import settings
from src.services.agent.service import AgentService
from src.services.llm.service import LLMService
from src.services.portfolio.service import PortfolioService


def build_agent() -> AgentService:
    """
    Initialise and return a fully-compiled ``AgentService``.

    Mirrors the service bootstrap performed in the FastAPI lifespan so the
    evaluation environment is identical to production.

    Returns:
        A ready-to-use ``AgentService`` with a compiled LangGraph and a
        fresh ``MemorySaver`` checkpointer.
    """
    portfolio_service = PortfolioService(data_path=settings.DATA_PATH)
    portfolio_service.initialize()

    llm_service = LLMService()

    agent_service = AgentService(
        portfolio_service=portfolio_service,
        llm_service=llm_service,
    )
    agent_service.initialize()
    return agent_service


def make_invoke_fn(agent_service: AgentService):
    """
    Return a ``(query: str) -> str`` callable wrapping ``AgentService.invoke``.

    TruLens's ``TruBasicApp`` expects a simple string-in / string-out function,
    so this adapter extracts ``final_answer`` from the full agent state dict.

    Args:
        agent_service: A fully-initialised ``AgentService``.

    Returns:
        A plain callable suitable for wrapping with ``TruBasicApp``.
    """
    def invoke(query: str) -> str:
        result = agent_service.invoke(query, thread_id="trulens_eval")
        return result.get("final_answer") or ""

    invoke.__name__ = "cortexre_agent"
    return invoke
