"""
api/exceptions.py
=================
Registers global FastAPI exception handlers for service-level errors.

``PortfolioError`` and ``AgentError`` carry their own ``status_code`` so the
handler can reflect the right HTTP status without branching.
"""

from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse
from loguru import logger

from src.services.portfolio.exceptions import PortfolioError
from src.services.agent.exceptions import AgentError


def register_exception_handlers(app) -> None:
    """Register global exception handlers on the FastAPI *app* instance."""

    @app.exception_handler(PortfolioError)
    @app.exception_handler(AgentError)
    async def service_error_handler(request: Request, exc: PortfolioError | AgentError):
        logger.error("{}: {} (status: {})", exc.__class__.__name__, exc.message, exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "error_type": exc.__class__.__name__},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception: {}", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An unexpected internal error occurred. Please try again later.",
                "error_type": "InternalServerError",
            },
        )
