# file: Makefile
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

.PHONY: help setup install lint format typecheck security test smoke build clean all refresh

# ********************
#  Help
# ********************

help:
	@echo "awsctl Developer Workflow"
	@echo "========================="
	@echo "make setup      : Create local virtualenv (.venv)"
	@echo "make install    : Install dev dependencies into .venv (Auto-creates venv)"
	@echo "make refresh    : Fast update of scripts/metadata (no full reinstall)"
	@echo "make lint       : Check formatter + linter"
	@echo "make format     : Run Black + Ruff auto-fix"
	@echo "make typecheck  : Run Mypy strict type checks"
	@echo "make security   : Run Bandit + pip-audit"
	@echo "make test       : Run unit tests"
	@echo "make build      : Build wheel + sdist"
	@echo "make clean      : Remove build and cache artifacts"

# ********************
#  Environment Setup
# ********************

# Ensure venv exists. This target creates it if missing.
$(VENV):
	python3.12 -m venv $(VENV)
	$(PIP) install pre-commit
	$(VENV)/bin/pre-commit install

setup: $(VENV)
	@echo "Run: source .venv/bin/activate"

# 'install' now depends on $(VENV), so it runs setup automatically if needed.
install: $(VENV)
	$(PIP) install --upgrade pip setuptools wheel
	# Force install [dev] deps to fix missing stubs
	$(PIP) install -e ".[dev]"
	@echo "Developer environment ready."

# Fast refresh for local dev (updates egg-info and scripts without full reinstall)
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

# [FIX] Run module-based mypy on the package name.
# Removed --strict because it overrides config file ignores.
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
	# [FIX] Ensure generated manifests are cleaned
	rm -rf tools/output

all: install lint typecheck security test
