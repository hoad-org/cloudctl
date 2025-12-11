# file: Makefile
# awsctl — Seamless Developer Makefile
# Zero Trust CLI — developer workflow

# ********************
#  Environment
# ********************

VENV := .venv
# [FIX] Use explicit relative path to ensure we use the venv binary, not system
PYTHON := ./$(VENV)/bin/python3
PIP := ./$(VENV)/bin/pip

SRC := src
TESTS := tests

.PHONY: help setup install lint format typecheck security test smoke build clean all refresh

# ********************
#  Help
# ********************

help:
	@echo "awsctl Developer Workflow"
	@echo "========================="
	@echo "make setup      : Create local virtualenv (.venv)"
	@echo "make install    : Install dev dependencies into .venv"
	@echo "make refresh    : Fast update of scripts (no full reinstall)"
	@echo "make lint       : Check formatter + linter"
	@echo "make format     : Run Black + Ruff auto-fix"
	@echo "make typecheck  : Run Mypy strict type checks"
	@echo "make security   : Run Bandit + pip-audit"
	@echo "make test       : Run unit tests"
	@echo "make clean      : Remove venv, build, and cache artifacts"

# ********************
#  Environment Setup
# ********************

# [FIX] Track the actual activate script, not just the directory.
$(VENV)/bin/activate:
	@echo "Creating virtual environment..."
	python3 -m venv $(VENV)
	$(PIP) install pre-commit
	$(VENV)/bin/pre-commit install
	@echo "Venv created."

setup: $(VENV)/bin/activate
	@echo "Environment setup complete."
	@echo "Run: source .venv/bin/activate"

install: $(VENV)/bin/activate
	@# Self-heal: If pip is missing (broken move), wipe and retry
	@test -f $(PIP) || (echo "Venv broken. Recreating..." && rm -rf $(VENV) && python3 -m venv $(VENV))
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -e ".[dev]"
	@echo "Developer environment ready."

refresh:
	$(PIP) install --no-deps -e .
	@echo "Local changes applied."

# ********************
#  Dev Commands
# ********************

lint:
	$(VENV)/bin/black --check $(SRC) $(TESTS)
	$(VENV)/bin/ruff check $(SRC) $(TESTS)
	$(VENV)/bin/mypy src

format:
	$(VENV)/bin/black $(SRC) $(TESTS)
	$(VENV)/bin/ruff check $(SRC) $(TESTS) --fix

typecheck:
	$(PYTHON) -m mypy -p awsctl

security:
	$(VENV)/bin/pip-audit
	$(VENV)/bin/bandit -r $(SRC) -s B101,B404,B603,B607

test:
	$(VENV)/bin/pytest -v --cov=awsctl --cov-report=term-missing

smoke:
	tools/comprehensive_smoke.sh

uat:
	tools/uat_enterprise.sh

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
	rm -rf build dist .coverage coverage.xml .tox *.egg-info src/*.egg-info
	find . -type d -name "smoke_artifacts" -exec rm -rf {} +
	rm -rf tools/output
	# [FIX] Nuke both the dev venv AND the smoke test venv to fix relocation issues
	rm -rf $(VENV)
	rm -rf .venv_smoke
	@echo "Clean complete."

all: install lint typecheck security test
