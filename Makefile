# ==============================================================================
# AWSCTL — Master Makefile
# ==============================================================================

PYTHON      := python3
PIP         := $(PYTHON) -m pip
POETRY      := poetry
SRC_DIR     := src/awsctl
TEST_DIR    := tests
MANIFEST_TOOL := tools/create_manifest.py

# Internal Shorthands
PYTEST      := $(POETRY) run pytest
SRC         := $(SRC_DIR)
TESTS       := $(TEST_DIR)

.PHONY: all bootstrap check clean lint format docs manifest smoke security install help

all: install check

help:
	@echo "awsctl Developer Workflow"
	@echo "========================="
	@echo "make install   : Install the package in editable mode"
	@echo "make bootstrap : Re-initialize Poetry and install all dependencies"
	@echo "make check     : Run tests with 80% coverage and explicit config"
	@echo "make lint      : Run quality checks (Ruff, Black, Mypy)"
	@echo "make format    : Auto-fix formatting and imports"
	@echo "make security  : Run security audits (Checkov, Bandit, Pip-audit)"

install:
	$(PIP) install -e .
	pyenv rehash

bootstrap:
	@echo "Initializing environment..."
	rm -f poetry.lock
	$(POETRY) install --with dev
	@echo "Environment ready."

check: format security
	@echo "Running tests with 80% coverage gate..."
	rm -f .coverage
	$(PYTEST) $(TESTS)/ \
		--cov=$(SRC) \
		--cov-config=.coveragerc \
		--cov-report=term-missing \
		--cov-report=html \
		--cov-fail-under=80

lint:   
	@echo "Linting..."
	$(POETRY) run ruff check $(SRC) $(TESTS)
	$(POETRY) run black --check $(SRC) $(TESTS)
	$(POETRY) run mypy $(SRC)

format:
	@echo "Auto-fixing formatting and imports..."
	$(POETRY) run ruff check $(SRC) $(TESTS) --fix
	$(POETRY) run black $(SRC) $(TESTS)

security:   
	@echo "Checking security..."
	$(POETRY) run checkov -d $(SRC) --quiet || true
	$(POETRY) run bandit -r $(SRC) -s B101,B404,B603,B607
	$(POETRY) run pip-audit

docs:
	$(PYTHON) tools/docs/lint_docs.py
	@echo "Documentation integrity verified."

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .coverage htmlcov .mypy_cache .ruff_cache 
	find . -name "__pycache__" -exec rm -rf {} +
	find . -name "*.pyc" -delete
	find . -name "awsctl.egg-info" -exec rm -rf {} +
	find . -name "*_manifest_*.txt" -delete

manifest:
	$(PYTHON) $(MANIFEST_TOOL)