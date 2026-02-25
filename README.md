# CortexRE — Real Estate Asset Management Agent

An AI-powered assistant for querying and analysing a real estate portfolio. Ask questions in plain English; the agent retrieves the right numbers from the underlying dataset and responds with a clear, formatted summary.

## Features

- **Natural language queries** — P&L, OER, growth metrics, expense breakdowns, and property comparisons
- **Multi-turn conversations** — session memory via LangGraph checkpointing
- **Provider-agnostic LLM** — swap between OpenAI, Anthropic, Ollama, or any LiteLLM-supported model with one env var
- **REST API** — FastAPI backend with Swagger docs at `/docs`
- **Chat UI** — Streamlit frontend for interactive exploration
- **TruLens evaluation** — LLM-graded answer relevance, groundedness, and context relevance

## Quick Start

### Prerequisites

- Python ≥ 3.13
- [`uv`](https://docs.astral.sh/uv/) package manager

### Setup

```bash
# 1. Install dependencies
make install

# 2. Configure environment
cp .env.example .env
# Edit .env: set LLM_MODEL and the matching API key
```

### Run

```bash
make run-api   # FastAPI backend  → http://localhost:8000
make run-ui    # Streamlit UI     → http://localhost:8501
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Docker

```bash
make docker-up    # Build and start all services
make docker-down  # Stop and remove containers
```

## LLM Provider

Set `LLM_MODEL` in `.env` to switch providers — no code changes needed:

```bash
LLM_MODEL=openai/gpt-4o-mini                   # OpenAI (default)
LLM_MODEL=anthropic/claude-3-5-haiku-20241022  # Anthropic
LLM_MODEL=ollama/llama3.2                       # Local Ollama
LLM_MODEL=gemini/gemini-1.5-flash              # Google
```

See [LiteLLM docs](https://docs.litellm.ai/docs/providers) for the full provider list.

## Sample Queries

| Query                                         | What it does                    |
| --------------------------------------------- | ------------------------------- |
| "What is the P&L for Building A in 2024?"     | Property-level income statement |
| "Compare all properties by NOI"               | Portfolio-wide ranking          |
| "Which property had the highest OER in 2025?" | Operating expense ratio         |
| "Show top expense drivers for 123 Main St"    | Expense breakdown               |
| "How did NOI grow from 2024 to 2025?"         | Year-over-year growth           |

## Evaluation

```bash
make evaluate-trulens
# or with the TruLens dashboard:
uv run src/evaluation/evaluation.py --dashboard
```

Results are saved to `tests/evaluation/trulens_report.json`.

## Project Layout

```
src/
├── agents/          # LangGraph nodes, tools, prompts, and workflow
├── api/             # FastAPI endpoints, schemas, exception handlers
├── core/            # Settings (pydantic-settings) and logging
├── evaluation/      # TruLens evaluation scripts
├── frontend/        # Streamlit chat UI
└── services/        # Business logic (portfolio, agent, LLM)
```

For architecture and design decisions, see [SOLUTION.md](SOLUTION.md).
