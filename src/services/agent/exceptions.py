from __future__ import annotations

from fastapi import status

class AgentError(Exception):
    """Base class for agent service errors."""
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class GraphNotInitializedError(AgentError):
    """Raised when the agent graph is accessed before compilation or on failure."""
    def __init__(self):
        super().__init__(
            "Agent workflow graph is not initialized. Please check logs for startup errors.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )

class AgentInvocationError(AgentError):
    """Raised when the agent fails during execution."""
    def __init__(self, detail: str):
        super().__init__(
            f"Agent execution failed: {detail}",
            status_code=status.HTTP_502_BAD_GATEWAY
        )
