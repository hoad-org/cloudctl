# file: Makefile
# awsctl — build, lint, and test automation

PYTHON ?= python3
SRC = src
TESTS = tests

.PHONY: help install lint format typecheck security test smoke build clean all

# --- Default Goal: Help ---
help:
	@echo "awsctl developer Makefile"
	@echo "========================="
	@echo "make setup      : Create local venv"
	@echo "make install    : Install dependencies in editable mode"
	@echo "make lint       : Check code style (Black + Ruff)"
	@echo "make format     : Fix code style (Black + Ruff)"
	@echo "make typecheck  : Run static typing (Mypy)"
	@echo "make security   : Audit dependencies and code (Bandit + Pip-audit)"
	@echo "make test       : Run unit tests"
	@echo "make smoke      : Run comprehensive integration smoke test"
	@echo "make build      : Build distribution artifacts (Wheel/Tarball)"
	@echo "make clean      : Remove all build and test artifacts"

# --- User Commands ---

setup:
	$(PYTHON) -m venv venv
	@echo "Run 'source venv/bin/activate' then 'make install'"

install:
	$(PYTHON) -m pip install --upgrade pip
	pip install -e .[dev]
	@echo "Run 'awsctl setup' to configure shell integration."

# --- Dev Commands ---

lint:
	black --check $(SRC) $(TESTS)
	ruff check $(SRC) $(TESTS)

format:
	black $(SRC) $(TESTS)
	ruff check $(SRC) $(TESTS) --fix

typecheck:
	$(PYTHON) -m mypy src --strict

security:
	pip-audit
	# [FIX] Use $(SRC) variable for consistency
	bandit -r $(SRC) -s B101,B404,B603,B607

test:
	pytest -v --cov=awsctl --cov-report=term-missing

smoke:
	tools/comprehensive_smoke.sh

build: clean
	$(PYTHON) -m build

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -rf build dist .coverage coverage.xml .tox
	find . -type d -name "smoke_artifacts" -exec rm -rf {} +
	# [CRITICAL] Remove egg-info to reset setuptools_scm version cache
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	# Remove venvs (Optional - aggressive clean)
	find . -type d -name ".venv" -exec rm -rf {} +
	find . -type d -name ".venv_smoke" -exec rm -rf {} +
	find . -type d -name "venv" -exec rm -rf {} +

all: install lint typecheck security test