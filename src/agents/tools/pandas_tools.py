"""
agents/tools/pandas_tools.py
============================
LangChain-compatible tool wrappers around ``AssetManagerAssistant``.

Design
------
Each tool is created via ``create_tools(df)``, a factory that closes over
the normalised DataFrame so the tools themselves only accept JSON-serialisable
arguments.  This lets the tools be registered with a LangGraph
``ToolNode`` / ``ToolExecutor`` and gives the LLM access to rich, parsed
docstrings through LangChain's ``parse_docstring=True`` option.

Usage::

    from src.agents.tools.pandas_tools import create_tools, ToolError

    tools = create_tools(df)          # list[BaseTool]
    result = tools[0].invoke({"property_name": "Building A", "year": 2024})
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from langchain_core.tools import tool

from src.services.portfolio.asset_manager import AssetManagerAssistant
from src.services.portfolio.normalization import OVERHEAD_PROPERTY


# ---------------------------------------------------------------------------
# Custom exception (re-raised as a user-facing message, not a stack trace)
# ---------------------------------------------------------------------------

class ToolError(Exception):
    """
    Raised when a tool cannot fulfil the request due to missing or
    inconsistent data — as opposed to a programming bug.

    The Error Handler node catches ``ToolError`` and converts its message
    into a user-friendly ``error_message`` in the agent state.
    """


# ---------------------------------------------------------------------------
# Internal helpers (not exposed as LangChain tools)
# ---------------------------------------------------------------------------

def _validate_property(df: pd.DataFrame, property_name: str) -> None:
    """Raise ToolError when *property_name* is not in the dataset."""
    known = set(df["property_name"].dropna().unique())
    if property_name not in known:
        close = [p for p in known if property_name.lower() in p.lower()]
        hint = f"  Did you mean: {', '.join(close[:3])}?" if close else ""
        raise ToolError(
            f"No property named '{property_name}' was found in the dataset.{hint}"
        )


def _validate_year(df: pd.DataFrame, year: int) -> None:
    """Raise ToolError when *year* has no matching rows."""
    if "year" not in df.columns:
        return
    available = set(df["year"].dropna().astype(int).unique())
    if year not in available:
        raise ToolError(
            f"No financial data is available for the year {year}. "
            f"Available years: {sorted(available)}."
        )


def _am(df: pd.DataFrame) -> AssetManagerAssistant:
    return AssetManagerAssistant(df)


def _fmt(value: float) -> str:
    """Format a float as a signed number with commas, e.g. -1,234,567.89."""
    sign = "-" if value < 0 else ""
    return f"{sign}{abs(value):,.2f}"


# ---------------------------------------------------------------------------
# Tool implementations (exposed both as functions and as LangChain tools)
# ---------------------------------------------------------------------------

def list_properties(df: pd.DataFrame) -> dict[str, Any]:
    """List all property names known in the dataset.

    Use this tool first whenever the user refers to a property by a
    partial name or asks which properties are available.  The returned
    list is also used to validate and fuzzy-match names before calling
    any financial tool.

    Returns:
        A dict with keys ``properties`` (list of names) and ``count``.
    """
    props = sorted(
        p for p in df["property_name"].dropna().unique()
        if p != OVERHEAD_PROPERTY
    )
    return {"label": "Known properties", "properties": props, "count": len(props)}


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------

def create_tools(df: pd.DataFrame) -> list[Any]:
    """
    Build and return all LangChain tools bound to *df*.

    Each tool is decorated with ``@tool(parse_docstring=True)`` so the LLM
    receives a structured description of the tool's purpose and parameters
    directly from the Google-style docstrings.

    Args:
        df: The normalised CortexRE DataFrame loaded at application startup.

    Returns:
        A list of ``BaseTool`` instances ready to be registered with a
        LangGraph ``ToolNode`` or passed to a ``create_react_agent``.
    """

    # ------------------------------------------------------------------
    # Tool 1 — List Properties
    # ------------------------------------------------------------------
    @tool(parse_docstring=True)
    def list_properties_tool() -> dict[str, Any]:
        """List all property names known in the dataset.

        Use this tool first whenever the user refers to a property by a
        partial name or asks which properties are available.  The returned
        list is also used to validate and fuzzy-match names before calling
        any financial tool.

        Returns:
            A dict with keys ``properties`` (list of names) and ``count``.
        """
        return list_properties(df)

    # ------------------------------------------------------------------
    # Tool 2 — P&L for a single property
    # ------------------------------------------------------------------
    @tool(parse_docstring=True)
    def get_property_pl(property_name: str, year: int | None = None) -> dict[str, Any]:
        """Return the P&L summary (revenue, expenses, NOI) for a single property.

        Use this tool when the user asks about profit and loss, revenue,
        expenses, or Net Operating Income (NOI) for a *specific* property.
        For portfolio-wide totals use ``get_portfolio_summary`` instead.

        Args:
            property_name: Exact property name as it appears in the dataset.
                           Call ``list_properties`` first if unsure of the name.
            year: Optional fiscal year (e.g. 2024 or 2025).  When omitted,
                  all years are aggregated into a single figure.

        Returns:
            A dict with ``revenue``, ``expenses``, ``noi`` (numeric) and their
            pre-formatted string equivalents (``revenue_fmt``, etc.).

        Raises:
            ToolError: If the property name does not exist in the dataset.
            ToolError: If no financial data is available for the requested year.
        """
        _validate_property(df, property_name)
        if year is not None:
            _validate_year(df, year)

        result = _am(df).get_property_pl(property_name, year)
        year_label = str(year) if year else "all years"
        return {
            "label": f"P&L for '{property_name}' ({year_label})",
            "property_name": property_name,
            "year": year,
            "revenue": result.get("revenue", 0),
            "expenses": result.get("expenses", 0),
            "noi": result.get("noi", 0),
            "revenue_fmt": _fmt(result.get("revenue", 0)),
            "expenses_fmt": _fmt(result.get("expenses", 0)),
            "noi_fmt": _fmt(result.get("noi", 0)),
        }

    # ------------------------------------------------------------------
    # Tool 3 — Portfolio summary
    # ------------------------------------------------------------------
    @tool(parse_docstring=True)
    def get_portfolio_summary(year: int | None = None) -> dict[str, Any]:
        """Return aggregated financials (revenue, expenses, NOI) across all properties.

        Use this tool when the user asks about the *entire portfolio* rather
        than a specific asset — e.g. "total revenue across all properties".
        Corporate/General overhead entries are excluded automatically.

        Args:
            year: Optional fiscal year filter.  When omitted, all years are
                  aggregated.

        Returns:
            A dict with ``revenue``, ``expenses``, ``noi`` and pre-formatted
            string versions of each value.
        """
        if year is not None:
            _validate_year(df, year)

        result = _am(df).get_portfolio_summary(year)
        year_label = str(year) if year else "all years"
        return {
            "label": f"Portfolio summary ({year_label})",
            "year": year,
            "revenue": result.get("revenue", 0),
            "expenses": result.get("expenses", 0),
            "noi": result.get("noi", 0),
            "revenue_fmt": _fmt(result.get("revenue", 0)),
            "expenses_fmt": _fmt(result.get("expenses", 0)),
            "noi_fmt": _fmt(result.get("noi", 0)),
        }

    # ------------------------------------------------------------------
    # Tool 4 — OER for a specific property and year
    # ------------------------------------------------------------------
    @tool(parse_docstring=True)
    def calculate_oer(property_name: str, year: int) -> dict[str, Any]:
        """Calculate the Operating Expense Ratio (OER) for a property in a given year.

        OER is defined as: |Total Expenses| / Total Revenue.
        A higher OER indicates that a larger share of revenue is consumed by
        operating costs, which is generally unfavourable for asset performance.

        Args:
            property_name: Exact property name as it appears in the dataset.
            year: The fiscal year to calculate OER for (e.g. 2024 or 2025).
                  Both arguments are required for an accurate calculation.

        Returns:
            A dict with ``oer`` (float, e.g. 0.35) and ``oer_pct``
            (formatted string, e.g. "35.0%").

        Raises:
            ToolError: If the property name does not exist in the dataset.
            ToolError: If no financial data is available for the requested year.
        """
        _validate_property(df, property_name)
        _validate_year(df, year)

        oer = _am(df).calculate_oer(property_name, year)
        return {
            "label": f"OER for '{property_name}' ({year})",
            "property_name": property_name,
            "year": year,
            "oer": oer,
            "oer_pct": f"{oer * 100:.1f}%",
        }

    # ------------------------------------------------------------------
    # Tool 5 — YoY growth metrics
    # ------------------------------------------------------------------
    @tool(parse_docstring=True)
    def get_growth_metrics(metric: str = "noi") -> dict[str, Any]:
        """Calculate year-over-year (YoY) growth for each property between 2024 and 2025.

        Use this tool when the user asks which properties grew or declined the
        most, or wants a ranked table of YoY performance.  Results are sorted
        from best to worst performer.

        Args:
            metric: The financial metric to measure growth on.
                    One of ``"noi"`` (default), ``"revenue"``, or ``"expenses"``.

        Returns:
            A dict with a ``rows`` list (each row has ``property_name``,
            ``growth`` as a float, and ``growth_pct`` as a string like "+12.3%"),
            plus convenience keys ``best_performer`` and ``worst_performer``.

        Raises:
            ToolError: If *metric* is not one of the accepted values.
        """
        valid = {"noi", "revenue", "expenses"}
        if metric not in valid:
            raise ToolError(
                f"Unknown metric '{metric}'. Valid options: {', '.join(valid)}."
            )

        results = _am(df).get_growth_metrics(metric)
        rows = []
        for prop, years_dict in results.items():
            if not years_dict:
                continue
            
            # The tool documentation focuses on 2024 -> 2025, but we'll take the latest available
            # year pair to be robust across different datasets.
            latest_label = sorted(years_dict.keys())[-1]
            val = years_dict[latest_label]
            
            rows.append({
                "property_name": prop,
                "growth": val,
                "growth_pct": f"{val * 100:+.1f}%",
            })

        # Sort from best to worst performer (descending growth)
        rows.sort(key=lambda x: x["growth"], reverse=True)

        return {
            "label": f"YoY growth by {metric} (2024 \u2192 2025)",
            "metric": metric,
            "rows": rows,
            "best_performer": rows[0]["property_name"] if rows else None,
            "worst_performer": rows[-1]["property_name"] if rows else None,
        }

    # ------------------------------------------------------------------
    # Tool 6 — Compare properties by metric
    # ------------------------------------------------------------------
    @tool(parse_docstring=True)
    def compare_properties(field: str = "noi") -> dict[str, Any]:
        """Rank all properties from highest to lowest by a selected financial metric.

        Use this tool when the user wants to compare or rank properties against
        each other — e.g. "which property has the highest revenue?" or "rank
        properties by expenses".

        Args:
            field: The metric to rank by.  Typically one of ``"noi"``
                   (default), ``"revenue"``, or ``"expenses"``.

        Returns:
            A dict with ``rows`` (each row has ``property_name``, ``value``
            as a float, and ``value_fmt`` as a dollar string) and
            ``top_property`` (name of the highest-ranked asset).
        """
        series = _am(df).compare_properties(field)
        rows = [
            {
                "property_name": prop,
                "value": val,
                "value_fmt": _fmt(val),
            }
            for prop, val in series.items()
        ]
        return {
            "label": f"Property comparison by {field}",
            "field": field,
            "rows": rows,
            "top_property": rows[0]["property_name"] if rows else None,
        }

    # ------------------------------------------------------------------
    # Tool 7 — Top expense drivers
    # ------------------------------------------------------------------
    @tool(parse_docstring=True)
    def top_expense_drivers(property_name: str | None = None) -> dict[str, Any]:
        """Identify the largest expense categories by total cost.

        Use this tool when the user asks what is driving costs up — either for
        the whole portfolio or for a specific property.  Results are sorted
        from largest to smallest expense (most negative first).

        Args:
            property_name: Optional property name to scope the analysis.
                           When omitted, the analysis covers the entire portfolio.

        Returns:
            A dict with ``rows`` (each row has ``category``, ``total`` as a
            float, and ``total_fmt`` as a dollar string) and
            ``largest_expense`` (the category with the highest cost).

        Raises:
            ToolError: If *property_name* is provided but does not exist in
                       the dataset.
        """
        if property_name:
            _validate_property(df, property_name)

        series = _am(df).top_expense_drivers(property_name)
        rows = [
            {"category": cat, "total": val, "total_fmt": _fmt(val)}
            for cat, val in series.items()
        ]
        scope = f"'{property_name}'" if property_name else "portfolio"
        return {
            "label": f"Top expense drivers ({scope})",
            "property_name": property_name,
            "rows": rows,
            "largest_expense": rows[0]["category"] if rows else None,
        }

    # ------------------------------------------------------------------
    # Tool 8 — Flexible Portfolio Query (Arbitrary groupings/filters)
    # ------------------------------------------------------------------
    @tool(parse_docstring=True)
    def query_portfolio(
        dimensions: list[str],
        metrics: list[str] = ["profit"],
        filters: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Flexible query engine for custom portfolio analysis across any dimensions.

        Use this tool as a fallback when the user asks a highly specific question
        that is not covered by the other tools (e.g. "What is the total profit
        by tenant?", "Show me expenses grouped by month for 2025", etc).

        Available dimensions to group by:
        "property_name", "date", "year", "month_val", "tenant_name", "ledger_type",
        "ledger_category", "description_en"

        Available metrics to sum:
        "profit"

        Args:
            dimensions: A list of column names to group the data by.
            metrics: A list of numerical columns to sum (defaults to ["profit"]).
            filters: Optional list of dictionaries with "column" and "value" keys. E.g. [{"column": "year", "value": 2025}]

        Returns:
            A dict with a `rows` key containing a list of aggregated results.
        """
        # Validate filters against known schema values
        if filters:
            valid_tenants = set(df["tenant_name"].dropna().unique()) if "tenant_name" in df.columns else set()
            valid_categories = set(df["ledger_category"].dropna().unique()) if "ledger_category" in df.columns else set()
            for f in filters:
                col = f.get("column")
                val = f.get("value")
                if col == "property_name":
                    _validate_property(df, str(val) if val is not None else "")
                elif col == "tenant_name" and val not in valid_tenants:
                    available = sorted(t for t in valid_tenants if t != "N/A")
                    raise ToolError(
                        f"No tenant named '{val}' in the dataset. "
                        f"Available tenants: {', '.join(available)}. "
                        f"Call get_schema_info to see tenants per property."
                    )
                elif col == "ledger_category" and val not in valid_categories:
                    raise ToolError(
                        f"No ledger category '{val}' in the dataset. "
                        f"Available categories: {', '.join(sorted(valid_categories))}. "
                        f"Call get_schema_info for the full list."
                    )

        rows = _am(df).query_portfolio(dimensions, metrics, filters)
        
        # Keep results manageable for the LLM context window by truncating huge responses
        if len(rows) > 50:
            return {
                "label": "Custom Query Result (Truncated)",
                "rows": rows[:50],
                "note": f"Result truncated. {len(rows)} total rows found, showing top 50.",
            }

        return {
            "label": "Custom Query Result",
            "rows": rows,
        }

    # ------------------------------------------------------------------
    # Tool 9 — Schema Info (dimension discovery)
    # ------------------------------------------------------------------
    @tool(parse_docstring=True)
    def get_schema_info() -> dict[str, Any]:
        """Return all valid dimension values available in the dataset.

        Call this tool FIRST whenever you are unsure about:
        - Which tenants exist (and which property they belong to)
        - Which ledger groups or ledger categories are available
        - Which years, quarters, or months are in the dataset

        Use the returned values as exact filter values in ``query_portfolio``
        or ``top_expense_drivers``.

        Returns:
            A dict with keys ``properties``, ``tenants_by_property``,
            ``all_tenants``, ``ledger_groups``, ``ledger_categories``,
            ``years``, ``quarters``, and ``months``.
        """
        return _am(df).get_schema_info()

    # ------------------------------------------------------------------
    # Tool 10 — Tenant Revenue Summary
    # ------------------------------------------------------------------
    @tool(parse_docstring=True)
    def get_tenant_summary(
        property_name: str | None = None,
        tenant_name: str | None = None,
    ) -> dict[str, Any]:
        """Return revenue per tenant, ranked from highest to lowest.

        Use this tool when the user asks:
        - "Who are my tenants?" or "Which tenants are in Building X?"
        - "What does Tenant Y pay in rent?"
        - "Which tenant generates the most revenue?"

        Args:
            property_name: Optional property to scope results to. When omitted,
                           returns tenants across all properties.
                           Call ``list_properties_tool`` first if unsure of the exact name.
            tenant_name: Optional specific tenant to filter to. When omitted,
                         all tenants are returned.
                         Call ``get_schema_info`` first if unsure of the exact tenant name.
                         If the name does not match any record, an empty result is returned.

        Returns:
            A dict with ``rows`` (each row has ``property_name``, ``tenant_name``,
            ``revenue`` as a float and ``revenue_fmt`` as a formatted string)
            and ``top_tenant`` (name of the highest-revenue tenant).

        Raises:
            ToolError: If ``property_name`` is provided but does not exist in the dataset.
        """
        if property_name:
            _validate_property(df, property_name)

        rows_raw = _am(df).get_tenant_summary(property_name, tenant_name)
        rows = [
            {
                "property_name": r["property_name"],
                "tenant_name": r["tenant_name"],
                "revenue": r["revenue"],
                "revenue_fmt": _fmt(r["revenue"]),
            }
            for r in rows_raw
        ]
        scope = (f" — {property_name}" if property_name else "") + (f" — {tenant_name}" if tenant_name else "")
        return {
            "label": f"Tenant revenue summary{scope}",
            "rows": rows,
            "top_tenant": rows[0]["tenant_name"] if rows else None,
        }

    # ------------------------------------------------------------------
    # Return all tools as a list
    # ------------------------------------------------------------------
    return [
        list_properties_tool,
        get_property_pl,
        get_portfolio_summary,
        calculate_oer,
        get_growth_metrics,
        compare_properties,
        top_expense_drivers,
        query_portfolio,
        get_schema_info,
        get_tenant_summary,
    ]
