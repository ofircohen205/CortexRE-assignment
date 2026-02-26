"""
services/llm/service.py
========================
Thin service layer that owns every interaction with the chat LLM.

Uses `LiteLLM <https://docs.litellm.ai>`_ as a unified proxy so the
application can route to **any** provider simply by changing the
``LLM_MODEL`` environment variable — no code changes needed.

LiteLLM model string examples
------------------------------
* ``openai/gpt-4o-mini``                  — OpenAI (requires OPENAI_API_KEY)
* ``anthropic/claude-3-5-haiku-20241022`` — Anthropic (requires ANTHROPIC_API_KEY)
* ``ollama/llama3.2``                     — local Ollama server (no key needed)
* ``gemini/gemini-1.5-flash``             — Google (requires GEMINI_API_KEY)

The full list of supported providers is at https://docs.litellm.ai/docs/providers

Usage::

    llm_service = LLMService()
    # Gate-keeping
    guard_result  = llm_service.check_input(query)
    # Critique
    critique      = llm_service.critique_response(query, tool_log, draft)
    # Output validation
    output_result = llm_service.check_output(query, known_properties, answer)
    # The research agent uses llm_service.chat_model directly via create_react_agent
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from loguru import logger

from src.agents.prompts.loader import load_prompt
from src.core.config import settings
from src.services.llm.exceptions import LLMInvocationError, LLMUnavailableError


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _litellm_completion(messages: list[dict[str, str]], *, model: str | None = None, response_format: dict | None = None) -> str:
    """
    Call LiteLLM with *messages* and return the response content string.

    Retries up to 3 times on rate-limit or transient errors, respecting the
    ``Retry-After`` header returned by the provider.

    Raises:
        LLMUnavailableError: If ``litellm`` is not installed.
        LLMInvocationError: For any error raised by LiteLLM at runtime.
    """
    try:
        import litellm
    except ImportError as exc:
        raise LLMUnavailableError(
            "litellm is not installed. Run: uv add litellm"
        ) from exc

    try:
        kwargs = {
            "model": model or settings.LLM_MODEL,
            "messages": messages,
            "temperature": settings.LLM_TEMPERATURE,
            "num_retries": 3,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = litellm.completion(**kwargs)
        return response.choices[0].message.content.strip()
    except Exception as exc:
        raise LLMInvocationError(str(exc)) from exc


def _parse_json(raw: str, context: str) -> dict[str, Any]:
    """Parse JSON from an LLM response, stripping markdown fences if present."""
    text = raw.strip()
    # Strip ```json ... ``` fences that some models add despite instructions
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("{} — could not parse JSON response: {} | raw={!r}", context, exc, raw)
        return {}


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class InputGuardResult:
    allowed: bool
    reason: str = ""


@dataclass
class CritiqueResult:
    approved: bool
    issues: list[str]
    revised_answer: str | None


@dataclass
class OutputGuardResult:
    valid: bool
    corrected_answer: str | None


# ---------------------------------------------------------------------------
# LLMService
# ---------------------------------------------------------------------------

class LLMService:
    """
    Central service for all LLM interactions.

    A single instance is created at startup and shared via
    ``app.state.llm_service``.  Swap providers at any time by changing
    ``LLM_MODEL`` in ``.env`` — the code is provider-agnostic.

    The ``chat_model`` property returns a LangChain ``ChatLiteLLM`` instance
    suitable for use with ``create_react_agent`` and ``bind_tools``.
    """

    def __init__(self) -> None:
        self._chat_model: Any = None

    # ------------------------------------------------------------------
    # LangChain chat model (used by the ReAct research agent)
    # ------------------------------------------------------------------

    @property
    def chat_model(self) -> Any:
        """
        Lazily initialise and return a ``ChatLiteLLM`` instance.

        This is a LangChain ``BaseChatModel`` that supports ``.bind_tools()``
        and works with ``langgraph.prebuilt.create_react_agent``.

        Raises:
            LLMUnavailableError: If ``langchain_litellm`` is not installed.
        """
        if self._chat_model is None:
            try:
                from langchain_litellm import ChatLiteLLM  # type: ignore[import]
            except ImportError as exc:
                raise LLMUnavailableError(
                    "langchain-litellm is not installed. Run: uv add langchain-litellm"
                ) from exc
            self._chat_model = ChatLiteLLM(
                model=settings.LLM_MODEL,
                temperature=settings.LLM_TEMPERATURE,
            )
        return self._chat_model

    # ------------------------------------------------------------------
    # Input Guard
    # ------------------------------------------------------------------

    def check_input(self, query: str) -> InputGuardResult:
        """
        Decide whether *query* should be allowed through to the research agent.

        Args:
            query: The raw natural-language question from the user.

        Returns:
            :class:`InputGuardResult` with ``allowed`` and optional ``reason``.
        """
        system_prompt = load_prompt("input_guard")
        try:
            raw = _litellm_completion([
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": query},
            ], response_format={"type": "json_object"})
            data = _parse_json(raw, "InputGuard")
            allowed = bool(data.get("allowed", True))
            reason = data.get("reason", "")
            logger.info(f"LLMService: InputGuard check complete | allowed={allowed} reason={reason!r}")
            return InputGuardResult(
                allowed=allowed,
                reason=reason,
            )
        except LLMUnavailableError:
            raise
        except Exception as exc:
            logger.warning("Input guard failed — defaulting to allow: {}", exc)
            return InputGuardResult(allowed=True)

    # ------------------------------------------------------------------
    # Critique Agent
    # ------------------------------------------------------------------

    def critique_response(
        self,
        query: str,
        tool_log: list[dict[str, Any]],
        draft_answer: str,
    ) -> CritiqueResult:
        """
        Review the *draft_answer* produced by the research agent.

        Args:
            query: The original user question.
            tool_log: List of tool calls made during research (name, args, result).
            draft_answer: The candidate answer from the research agent.

        Returns:
            :class:`CritiqueResult` with ``approved``, ``issues``, and
            ``revised_answer``.
        """
        system_prompt = load_prompt("critique_agent")
        user_content = (
            f"User question: {query}\n\n"
            f"Tool call log:\n{json.dumps(tool_log, indent=2, default=str)}\n\n"
            f"Draft answer: {draft_answer}"
        )
        try:
            raw = _litellm_completion([
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content},
            ], response_format={"type": "json_object"})
            data = _parse_json(raw, "CritiqueAgent")
            approved = bool(data.get("approved", True))
            issues = data.get("issues", [])
            logger.info(f"LLMService: Critique complete | approved={approved} issues_count={len(issues)}")
            return CritiqueResult(
                approved=approved,
                issues=issues,
                revised_answer=data.get("revised_answer"),
            )
        except LLMUnavailableError:
            raise
        except Exception as exc:
            logger.warning("Critique agent failed — defaulting to approve: {}", exc)
            return CritiqueResult(approved=True, issues=[], revised_answer=None)

    # ------------------------------------------------------------------
    # Output Guard
    # ------------------------------------------------------------------

    def check_output(
        self,
        query: str,
        known_properties: list[str],
        answer: str,
    ) -> OutputGuardResult:
        """
        Validate the final candidate answer before returning it to the user.

        Args:
            query: The original user question.
            known_properties: All valid property names in the dataset.
            answer: The answer to validate.

        Returns:
            :class:`OutputGuardResult` with ``valid`` and ``corrected_answer``.
        """
        # Cheap pre-pass: strip stray currency symbols before LLM call
        for sym in ("$", "€", "£"):
            answer = answer.replace(sym, "")

        system_prompt = load_prompt("output_guard")
        prop_list = ", ".join(known_properties)
        user_content = (
            f"User question: {query}\n\n"
            f"Known property names: {prop_list}\n\n"
            f"Candidate answer: {answer}"
        )
        try:
            raw = _litellm_completion([
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content},
            ], response_format={"type": "json_object"})
            data = _parse_json(raw, "OutputGuard")
            valid = bool(data.get("valid", True))
            logger.info(f"LLMService: OutputGuard check complete | valid={valid} "
                        f"has_correction={'corrected_answer' in data and data['corrected_answer']}")
            return OutputGuardResult(
                valid=valid,
                corrected_answer=data.get("corrected_answer"),
            )
        except LLMUnavailableError:
            raise
        except Exception as exc:
            logger.warning("Output guard failed — returning answer as-is: {}", exc)
            return OutputGuardResult(valid=True, corrected_answer=None)
