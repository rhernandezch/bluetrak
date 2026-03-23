.PHONY: run test test-integration lint typecheck fmt check test-telegram build

# ── Development ─────────────────────────────────────────────────────────────

run:
	uv run bluetrak

test:
	uv run pytest tests/ -v

test-integration:
	uv run pytest tests/test_integration.py -v

lint:
	uv run ruff check src/ tests/

typecheck:
	uv run mypy src/

fmt:
	uv run ruff format src/ tests/

check: lint typecheck test

# ── Utilities ───────────────────────────────────────────────────────────────

test-telegram:
	uv run bluetrak-test-telegram

# ── Docker ──────────────────────────────────────────────────────────────────

build:
	docker build -t bluetrak .
