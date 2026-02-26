"""
scripts/smoke_test.py
======================
Run a handful of example queries through the full agent workflow and print
the results.  No TruLens required — useful for quick sanity checks after
prompt or tool changes.

Usage::

    uv run scripts/smoke_test.py
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.evaluation.runner import build_agent

EXAMPLES = [
    "What is the total P&L for all my properties in year 2024?",
    "Which building has the highest revenue and which has the highest expense?",
    "What was the NOI for Building 120 in 2024?",
    "What is the OER for Building 17 in 2024?",
    "Which property had the best NOI growth from 2024 to 2025?",
]


def main() -> None:
    print("Initialising agent...\n")
    agent = build_agent()

    for i, query in enumerate(EXAMPLES, start=1):
        thread_id = str(uuid.uuid4())
        print(f"{'=' * 60}")
        print(f"[{i}/{len(EXAMPLES)}] {query}")
        print("-" * 60)
        result = agent.invoke(query, thread_id=thread_id)
        answer = result.get("final_answer") or "(no answer)"
        revisions = result.get("revision_count", 0)
        blocked = result.get("blocked", False)
        print(f"Answer    : {answer}")
        print(f"Revisions : {revisions}  |  Blocked: {blocked}")
        print()


if __name__ == "__main__":
    main()
