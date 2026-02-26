import time
from fastapi import APIRouter, Depends
from loguru import logger

from src.api.deps import get_agent_service, get_portfolio_service
from src.api.schemas import QueryRequest, QueryResponse, ErrorResponse
from src.services.agent.service import AgentService
from src.services.portfolio.service import PortfolioService

router = APIRouter()

@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Natural language query",
    responses={
        200: {"model": QueryResponse, "description": "Successful agent response"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        502: {"model": ErrorResponse, "description": "Agent/LLM execution failure"},
    },
)
async def query_agent(
    request: QueryRequest,
    agent_service: AgentService = Depends(get_agent_service),
):
    """
    Submit a real-estate question and get a business-friendly answer from the agent.
    """
    query = request.query
    logger.info(f"API: Received user query: {query!r}")
    start_time = time.time()

    try:
        # Invoke the agent service (handles graph traversal and checkpointer persistence)
        logger.debug("API: Dispatching query to AgentService")
        # Use dynamic thread ID from request if provided
        thread_id = request.thread_id or "default_session"
        result = agent_service.invoke(query, thread_id=thread_id)
        
        answer = result.get("final_answer") or "No answer could be generated."
        blocked = result.get("blocked", False)
        block_reason = result.get("block_reason")

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(
            f"API: Completed query in {elapsed_ms:.0f}ms | blocked={blocked} "
            f"| answer_length={len(answer)}"
        )

        return QueryResponse(
            answer=answer,
            blocked=blocked,
            block_reason=block_reason,
            intermediate_steps=result.get("steps", []),
        )
    except Exception as exc:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.error(f"API: Query failed after {elapsed_ms:.0f}ms | error={exc}")
        raise


@router.get(
    "/properties",
    summary="List portfolio properties",
    responses={
        200: {"description": "List of property names"},
        404: {"model": ErrorResponse, "description": "Dataset not found"},
    },
)
async def list_properties(
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """
    Returns a distinct list of property names found in the dataset.
    """
    unique_props = portfolio_service.property_list
    return {"properties": unique_props}


@router.get(
    "/eda/stats",
    summary="Portfolio statistics for EDA",
    responses={
        200: {"description": "Aggregated stats for charts"},
        404: {"model": ErrorResponse, "description": "Dataset not found"},
    },
)
async def get_eda_stats(
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """
    Returns aggregated revenue, expense, and NOI data for frontend visualization.
    """
    stats = portfolio_service.get_eda_stats()
    return stats


@router.get("/health", summary="Health check")
async def health_check():
    """Liveness probe to verify the service is running and ready."""
    return {"status": "ok", "agent": "ready"}
