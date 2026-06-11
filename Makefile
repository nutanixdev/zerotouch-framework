UV := $(or $(shell command -v uv 2>/dev/null),$(HOME)/.local/bin/uv)

.PHONY: help lint format test test-functional typecheck install-hooks ci security

help:
	@echo "Available commands:"
	@echo "  make install-hooks      - Install pre-commit hooks (RUN THIS FIRST)"
	@echo "  make lint               - Run ruff linter"
	@echo "  make format             - Format code with ruff"
	@echo "  make test               - Run unit tests with coverage (fast, ~30s)"
	@echo "  make test-functional    - Run functional tests (slow, 9+ min, requires PC access)"
	@echo "  make typecheck          - Run mypy type checking"
	@echo "  make security           - Run bandit security scan"
	@echo "  make ci                 - Run all checks (format, lint, typecheck, test)"

install-hooks:
	@echo "Installing pre-commit hooks..."
	$(UV) run pre-commit install
	@echo "Pre-commit hooks installed. Code will be formatted on each commit."

lint:
	$(UV) run ruff check .

format:
	$(UV) run ruff format .

typecheck:
	$(UV) run mypy ztf/ --ignore-missing-imports

test:
	$(UV) run pytest tests/ --ignore=tests/functional -v --cov=ztf --cov-report=term-missing --cov-fail-under=95

test-functional:
	$(UV) run pytest tests/functional -v --timeout=600

security:
	$(UV) run bandit -r ztf/ -c pyproject.toml

ci: format lint typecheck test
	@echo "All checks passed!"
