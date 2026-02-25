"""
evaluation/feedbacks.py
========================
TruLens feedback function definitions for the CortexRE agent.

Provides three LLM-graded signals:

* **Answer Relevance** — does the answer address the user's question?
* **Groundedness** — is the answer supported by the retrieved data?
* **Context Relevance** — is the context passed to the LLM on-topic?
"""

from __future__ import annotations

from trulens.core import Feedback
from trulens.providers.openai import OpenAI as TruOpenAI


def build_feedbacks(provider: TruOpenAI) -> list[Feedback]:
    """
    Build the three core LLM-graded feedback functions.

    Args:
        provider: A TruLens ``OpenAI`` provider instance used to score responses.

    Returns:
        A list of three configured ``Feedback`` objects ready to be passed to
        ``TruBasicApp``.
    """
    f_answer_relevance = (
        Feedback(provider.relevance, name="Answer Relevance")
        .on_input_output()
    )

    f_groundedness = (
        Feedback(
            provider.groundedness_measure_with_cot_reasons,
            name="Groundedness",
        )
        .on_output()
        .on_output()
        .aggregate(lambda scores: sum(scores) / len(scores) if scores else 0.0)
    )

    f_context_relevance = (
        Feedback(provider.context_relevance, name="Context Relevance")
        .on_input()
        .on_output()
        .aggregate(lambda scores: sum(scores) / len(scores) if scores else 0.0)
    )

    return [f_answer_relevance, f_groundedness, f_context_relevance]
