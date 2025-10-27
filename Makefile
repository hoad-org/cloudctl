# ============================================================
# AWSCTL - Makefile
# ------------------------------------------------------------
# Unified developer workflow for building, testing, linting,
# installing, and packaging the awsctl CLI utility.
#
# Compatible with macOS, Linux, and WSL.
# ============================================================

# Python executables
PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
TOX ?= tox

# Default virtual environment
VENV_DIR := venv
VENV_BIN := $(VENV_DIR)/bin
ACTIVATE := source $(VENV_BIN)/activate

# Colors for output
BOLD := \033[1m
RESET := \033[0m
GREEN := \033[32m
CYAN := \033[36m
YELLOW := \033[33m

.PHONY: all setup clean reinstall test lint coverage build install uninstall fmt check-env shell

all: setup test

setup:
	@echo "$(CYAN)Setting up development environment...$(RESET)"
	$(PYTHON) -m venv $(VENV_DIR)
	@$(ACTIVATE) && $(PIP) install -U pip setuptools wheel tox
	@$(ACTIVATE) && $(PIP) install -e ".[dev]"
	@echo "$(GREEN)Environment ready. Run: source $(VENV_DIR)/bin/activate$(RESET)"

clean:
	@echo "$(YELLOW)Cleaning...$(RESET)"
	rm -rf $(VENV_DIR) dist build *.egg-info .tox .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -f ~/.aws/awsctl-context.json ~/.awsctl/orgs.yaml
	@echo "$(GREEN)Clean complete.$(RESET)"

reinstall: clean
	@echo "$(CYAN)Reinstalling awsctl...$(RESET)"
	@$(MAKE) setup

test:
	@echo "$(CYAN)Running tests via tox...$(RESET)"
	@$(TOX) -e py313
	@echo "$(GREEN)Tests passed.$(RESET)"

lint:
	@echo "$(CYAN)Running lint/type checks...$(RESET)"
	@$(TOX) -e lint
	@echo "$(GREEN)Lint clean.$(RESET)"

coverage:
	@echo "$(CYAN)Coverage report...$(RESET)"
	@$(TOX) -e coverage

build:
	@echo "$(CYAN)Building package...$(RESET)"
	@$(ACTIVATE) && python -m build
	@echo "$(GREEN)Build complete.$(RESET)"

install:
	@echo "$(CYAN)Installing via pipx...$(RESET)"
	@if ! command -v pipx >/dev/null 2>&1; then \
		echo "Installing pipx..."; \
		brew install pipx || $(PYTHON) -m pip install --user pipx; \
	fi
	pipx install .
	@echo "$(GREEN)awsctl installed.$(RESET)"

uninstall:
	@echo "$(YELLOW)Uninstalling awsctl...$(RESET)"
	-pipx uninstall awsctl || true
	sed -i.bak '/AWSCTL SHELL INTEGRATION (auto-installed)/,/END AWSCTL SHELL INTEGRATION/d' ~/.zshrc 2>/dev/null || true
	sed -i.bak '/AWSCTL SHELL INTEGRATION (auto-installed)/,/END AWSCTL SHELL INTEGRATION/d' ~/.bashrc 2>/dev/null || true
	rm -f ~/.aws/awsctl-context.json ~/.awsctl/orgs.yaml
	@echo "$(GREEN)Uninstall complete.$(RESET)"

fmt:
	@echo "$(CYAN)Formatting...$(RESET)"
	@$(ACTIVATE) && black awsctl tests
	@echo "$(GREEN)Done.$(RESET)"

check-env:
	@echo "$(CYAN)Environment check...$(RESET)"
	@echo "Python: $$($(PYTHON) --version)"
	@echo "AWS CLI: $$(aws --version 2>&1 || echo 'Missing')"
	@echo "jq: $$(jq --version 2>&1 || echo 'Missing')"

shell:
	@echo "$(CYAN)Interactive shell...$(RESET)"
	@$(ACTIVATE) && exec $$SHELL

# -------------------------
# Summary
# - Aligned dev install to extras [dev].
# - Added cleanup of .tox, caches.
# -------------------------