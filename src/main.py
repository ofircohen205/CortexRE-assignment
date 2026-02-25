"""
main.py
=======
FastAPI application entry point for the CortexRE Asset Management Agent.
Initializes logging, manages the dataset lifespan, and registers API routers
and global exception handlers.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.services.portfolio.service import PortfolioService
from src.services.agent.service import AgentService
from src.services.llm.service import LLMService
from src.api.endpoints import router as api_router
from src.api.exceptions import register_exception_handlers
from src.core.config import settings
from src.core.logging_config import setup_logging

# Initialize logging immediately
setup_logging(level="INFO")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initializes application resources (Portfolio and Agent services) 
    exactly once on startup and attaches them to the app state.
    """
    logger.info("Starting up CortexRE Asset Management Agent...")
    
    try:
        # Initialize Portfolio Service (Data Layer)
        portfolio_service = PortfolioService(data_path=settings.DATA_PATH)
        portfolio_service.initialize()
        
        # Initialize LLM Service (all OpenAI interactions)
        llm_service = LLMService()

        # Initialize Agent Service (Logic/Persistence Layer)
        agent_service = AgentService(portfolio_service=portfolio_service, llm_service=llm_service)
        agent_service.initialize()
        
        # Attach to app state for Dependency Injection
        app.state.portfolio_service = portfolio_service
        app.state.llm_service = llm_service
        app.state.agent_service = agent_service
        
        logger.info("All services initialized and ready.")
    except Exception as exc:
        logger.exception(f"Startup failed: {exc}")
        # In a production environment, we might want to halt startup here.
        # For this prototype, we rely on the Exception Handlers to report errors down the line.

    yield

    logger.info("Shutting down service.")


def create_app() -> FastAPI:
    """Factory for creating and configuring the FastAPI application."""
    app = FastAPI(
        title="CortexRE Asset Management Agent",
        description=(
            "A LangGraph system for natural-language real-estate "
            "asset management queries."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception Handlers
    register_exception_handlers(app)

    # Routers
    app.include_router(api_router)

    return app


app = create_app()
