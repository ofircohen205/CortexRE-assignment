"""
services/llm/exceptions.py
===========================
Exceptions raised by the LLM service layer.
"""

from __future__ import annotations

from fastapi import status


class LLMError(Exception):
    """Base class for LLM service errors."""

    def __init__(self, message: str, status_code: int = status.HTTP_502_BAD_GATEWAY) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class LLMUnavailableError(LLMError):
    """Raised when the LLM client cannot be instantiated (missing dependency / bad key)."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            f"LLM is unavailable: {detail}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class LLMInvocationError(LLMError):
    """Raised when an LLM call fails at runtime (network error, malformed response, …)."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            f"LLM invocation failed: {detail}",
            status_code=status.HTTP_502_BAD_GATEWAY,
        )
