.PHONY: help install run-api run-ui docker-up docker-down clean test lint evaluate-trulens

help:
	@echo "Usage:"
	@echo "  make install             Install dependencies using uv"
	@echo "  make run-api             Run FastAPI backend locally"
	@echo "  make run-ui              Run Streamlit UI locally"
	@echo "  make docker-up           Start services using Docker Compose"
	@echo "  make docker-down         Stop services using Docker Compose"
	@echo "  make test                Run tests"
	@echo "  make test-verbose        Run tests with verbose output"
	@echo "  make test-coverage       Run tests with coverage report"
	@echo "  make lint                Run ruff linting"
	@echo "  make evaluate            Run TruLens LLM-graded evaluation"
	@echo "  make clean               Clean up cache files"

install:
	uv sync

run-api:
	uv run python src/main.py

run-ui:
	uv run streamlit run src/frontend/app.py

docker-up:
	docker compose -p cortex-re up -d --build --force-recreate

docker-down:
	docker compose down --volumes --remove-orphans

test:
	PYTHONPATH=. uv run --no-cache pytest tests/

test-verbose:
	PYTHONPATH=. uv run --no-cache pytest -vv tests/

test-coverage:
	PYTHONPATH=. uv run --no-cache pytest --cov=src tests/

lint:
	uv run ruff check src/

evaluate:
	PYTHONPATH=. uv run --no-cache python -m src.evaluation.evaluation

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -rf .coverage htmlcov
