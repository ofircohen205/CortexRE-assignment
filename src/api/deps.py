from __future__ import annotations

from fastapi import Request
from src.services.portfolio.service import PortfolioService
from src.services.agent.service import AgentService

def get_portfolio_service(request: Request) -> PortfolioService:
    """Retrieves the PortfolioService singleton from the application state."""
    return request.app.state.portfolio_service

def get_agent_service(request: Request) -> AgentService:
    """Retrieves the AgentService singleton from the application state."""
    return request.app.state.agent_service
