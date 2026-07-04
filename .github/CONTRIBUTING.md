# Contributing to awsctl

## Getting Started

```bash
git clone https://github.com/BT-IT-Infrastructure-CloudOps/aws-terraform-infra-cloudops-awsctl.git
cd aws-terraform-infra-cloudops-awsctl
poetry install --with dev
poetry run pytest
```

## Development Requirements

- Python 3.12+
- Poetry
- AWS CLI v2 (for manual testing against real accounts)

## Making Changes

1. Create a branch from `main`
2. Make your changes
3. Run the full test suite: `poetry run pytest`
4. Run linting: `poetry run ruff check . && poetry run black --check .`
5. Run security scan: `poetry run bandit -r src/ -ll`
6. Open a pull request against `main`

## Pull Request Guidelines

- Keep PRs focused — one logical change per PR
- All CI checks must pass before merge
- Security-sensitive paths (`src/awsctl/providers/`, `src/awsctl/guardrails.py`, `src/awsctl/use_exports.py`, `.github/workflows/`) require CloudOps team review
- Include tests for new behaviour; maintain or improve coverage
- Update the README changelog section for user-visible changes

## Reporting Security Issues

See [SECURITY.md](SECURITY.md). Do **not** open a public issue for vulnerabilities.

## Code Style

- Formatter: `black` (enforced in CI)
- Linter: `ruff` (enforced in CI)
- All new code must pass `bandit -ll` at medium+ severity
