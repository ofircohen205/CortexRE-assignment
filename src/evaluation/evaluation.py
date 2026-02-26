"""
evaluation/evaluation.py
=========================
TruLens-based evaluation for the CortexRE LangGraph agent.

Orchestrates the full evaluation loop:
  1. Load test cases from ``tests/evaluation/ground_truth.json``
  2. Bootstrap the agent via :mod:`src.evaluation.runner`
  3. Open a TruLens session and wrap the agent with ``TruBasicApp``
  4. Run each query and collect LLM-graded feedback scores
  5. Print a summary and persist results to JSON + SQLite

Usage::

    uv run src/evaluation/evaluation.py [--dashboard] [--port 8502]

Flags::

    --dashboard   Launch the TruLens Streamlit dashboard after evaluation.
    --port PORT   Dashboard port (default: 8502).
"""

from __future__ import annotations

import pandas as pd
import argparse
import json
import math
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

# ---- LangChain 0.3 Migration Bridge ------------------------------------------
# TruLens 1.3.0 still relies on the legacy 'langchain.schema' namespace for
# some providers. We monkey-patch it here to map to langchain_core.
try:
    import langchain.schema  # noqa: F401
except ImportError:
    import langchain_core.outputs
    schema = ModuleType("langchain.schema")
    sys.modules["langchain.schema"] = schema
    schema.Generation = langchain_core.outputs.Generation
# ------------------------------------------------------------------------------

from loguru import logger

from src.core.config import settings
from src.evaluation.feedbacks import build_feedbacks
from src.evaluation.ground_truth import load_or_generate
from src.evaluation.runner import build_agent, make_invoke_fn

try:
    from trulens.core import TruSession
    from trulens.apps.basic import TruBasicApp
    from trulens.providers.openai import OpenAI as TruOpenAI
except ImportError as exc:
    logger.error(
        "TruLens packages not found. Install with:\n"
        "  uv add trulens-core trulens-providers-openai"
    )
    raise SystemExit(1) from exc

_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def run_evaluation(dashboard: bool = False, port: int = 8502) -> None:
    """
    Run the full TruLens evaluation pipeline.

    Args:
        dashboard: If ``True``, launch the TruLens Streamlit dashboard on
                   completion.
        port: Port for the TruLens dashboard (default: 8502).
    """
    # ---- Load ground truth ---------------------------------------------------
    gt_path = _ROOT / "tests" / "evaluation" / "ground_truth.json"
    ground_truth: list[dict[str, Any]] = load_or_generate(gt_path)
    logger.info("Loaded {} test cases", len(ground_truth))

    # ---- Services ------------------------------------------------------------
    logger.info("Initialising agent services...")
    agent_service = build_agent()
    invoke_fn = make_invoke_fn(agent_service)

    # ---- TruLens session -----------------------------------------------------
    db_path = _ROOT / "tests" / "evaluation" / "trulens.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Opening TruLens session at {}", db_path)
    session = TruSession(database_url=f"sqlite:///{db_path}")
    session.reset_database()  # fresh run; remove this line to accumulate runs

    # ---- Provider + feedbacks ------------------------------------------------
    provider = TruOpenAI(api_key=settings.OPENAI_API_KEY)
    feedbacks = build_feedbacks(provider)

    # ---- Wrap the agent ------------------------------------------------------
    tru_app = TruBasicApp(
        invoke_fn,
        app_name="CortexRE Agent",
        app_version="1.0",
        feedbacks=feedbacks,
    )

    # ---- Evaluation loop -----------------------------------------------------
    logger.info("Starting evaluation over {} queries...", len(ground_truth))
    errors: list[dict] = []
    query_results: list[dict] = []
    record_ids: list[str] = []

    for i, case in enumerate(ground_truth, start=1):
        import time
        if i > 1:
            time.sleep(4)  # stay under the 30K TPM rate limit

        query = case["query"]
        logger.info("[{}/{}] {}", i, len(ground_truth), query)
        try:
            with tru_app as recording:
                response = tru_app.app(query)
            rec = recording.get()
            record_ids.append(rec.record_id)
            query_results.append({
                "query": query,
                "response": response,
                "record_id": rec.record_id,
                "expected": case.get("expected_values"),
                "expected_intent": case.get("expected_intent"),
            })
        except Exception as exc:
            logger.exception("Failed on query {!r}: {}", query, exc)
            errors.append({"query": query, "error": str(exc)})

    # ---- Wait for feedback ---------------------------------------------------
    if record_ids:
        logger.info("Waiting for feedback results to be computed (this may take a minute)...")
        feedback_names = [f.name for f in feedbacks]
        try:
            session.wait_for_feedback_results(
                record_ids=record_ids,
                feedback_names=feedback_names,
                timeout=120,
            )
        except Exception as exc:
            logger.warning("Timed out or failed waiting for TruLens feedback: {}", exc)
            logger.warning("The report will include partial scores if available.")

    # ---- Results -------------------------------------------------------------
    records, feedback_col_names = session.get_records_and_feedback(
        app_ids=["CortexRE Agent"]
    )

    print("\n" + "=" * 60)
    print("TRULENS EVALUATION REPORT")
    print("=" * 60)
    print(f"Total queries evaluated : {len(ground_truth)}")
    print(f"Errors                  : {len(errors)}")
    print()

    summary: dict[str, float | None] = {}
    for col in feedback_col_names:
        if col in records.columns:
            mean_score = records[col].dropna().mean()
            summary[col] = round(float(mean_score), 4) if not math.isnan(mean_score) else None
            print(f"  {col:<30} {mean_score:.3f}")
    print("=" * 60)

    # ---- Enrich query results with feedback scores ---------------------------
    logger.debug("Enriching {} results with feedback scores...", len(query_results))
    if query_results:
        logger.debug("First query result keys: {}", query_results[0].keys())
    logger.debug("Records columns: {}", list(records.columns))

    for res in query_results:
        rid = res.get("record_id")
        if not rid:
            logger.warning("No record_id found for query: {}", res.get("query"))
            continue

        if "record_id" not in records.columns:
            logger.error("'record_id' column missing from TruLens records dataframe!")
            break

        matching_rows = records[records["record_id"] == rid]
        if not matching_rows.empty:
            row = matching_rows.iloc[0]
            res["feedback"] = {
                col: float(row[col]) if not isinstance(row[col], (type(pd.NA), type(None))) and not (isinstance(row[col], float) and math.isnan(row[col])) else None
                for col in feedback_col_names if col in row.index
            }

    # ---- Save JSON report ----------------------------------------------------
    report_path = _ROOT / "tests" / "evaluation" / "trulens_report.json"
    with open(report_path, "w") as fh:
        json.dump(
            {
                "total_cases": len(ground_truth),
                "errors": len(errors),
                "overall_feedback_scores": summary,
                "query_results": query_results,
                "error_details": errors,
            },
            fh,
            indent=2,
        )
    logger.info("Report saved to {}", report_path)
    logger.info("TruLens traces saved to {}", db_path)

    # ---- Optional dashboard --------------------------------------------------
    if dashboard:
        logger.info("Launching TruLens dashboard on port {}...", port)
        session.run_dashboard(port=port)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run TruLens evaluation for the CortexRE agent."
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Launch the TruLens Streamlit dashboard after evaluation.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("TRULENS_DASHBOARD_PORT", "8502")),
        help="Dashboard port (default: 8502).",
    )
    args = parser.parse_args()
    run_evaluation(dashboard=args.dashboard, port=args.port)
