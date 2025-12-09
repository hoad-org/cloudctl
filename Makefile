# awsctl — Seamless Developer Makefile
# Zero Trust CLI — developer workflow

# ********************
#  Environment
# ********************

VENV := .venv
PYTHON := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip

SRC := src
TESTS := tests

.PHONY: help setup install lint format typecheck security test smoke build clean all

# ********************
#  Help
# ********************

help:
	@echo "awsctl Developer Workflow"
	@echo "========================="
	@echo "make setup      : Create local virtualenv (.venv)"
	@echo "make install    : Install dev dependencies into .venv"
	@echo "make lint       : Check formatter + linter"
	@echo "make format     : Run Black + Ruff auto-fix"
	@echo "make typecheck  : Run Mypy strict type checks"
	@echo "make security   : Run Bandit + pip-audit"
	@echo "make test       : Run unit tests"
	@echo "make smoke      : Run comprehensive smoke test"
	@echo "make build      : Build wheel + sdist"
	@echo "make clean      : Remove build and cache artifacts"

# ********************
#  Environment Setup
# ********************

setup:
	python3.12 -m venv $(VENV)
	$(PIP) install pre-commit
	$(VENV)/bin/pre-commit install
	@echo "Run: source .venv/bin/activate"

install:
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -e ".[dev]" -c constraints.txt
	@echo "Developer environment ready."

# ********************
#  Dev Commands
# ********************

lint:
	$(VENV)/bin/black --check $(SRC) $(TESTS)
	$(VENV)/bin/ruff check $(SRC) $(TESTS)

format:
	$(VENV)/bin/black $(SRC) $(TESTS)
	$(VENV)/bin/ruff check $(SRC) $(TESTS) --fix

typecheck:
	$(PYTHON) -m mypy $(SRC) --strict

security:
	$(VENV)/bin/pip-audit
	$(VENV)/bin/bandit -r $(SRC) -s B101,B404,B603,B607

test:
	$(VENV)/bin/pytest -v --cov=awsctl --cov-report=term-missing

smoke:
	tools/comprehensive_smoke.sh

build: clean
	$(PYTHON) -m build

# ********************
#  Cleanup (Safe)
# ********************

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -rf build dist .coverage coverage.xml .tox

all: install lint typecheck security test
