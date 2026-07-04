# Contributing to cloudctl

## Getting Started

```bash
git clone https://github.com/hoad-org/cloudctl.git
cd cloudctl
python3.12 -m pip install -e ".[dev]"
python -m pytest -q
```

## Development Requirements

- Python 3.12+
- AWS CLI v2 (for manual testing against real accounts)

## Making Changes

1. Create a branch from `main`
2. Make your changes
3. Run the full test suite: `python -m pytest -q`
4. Run linting: `ruff check . && black --check .`
5. Type-check: `mypy src/cloudctl`
6. Open a pull request against `main`

## Pull Request Guidelines

- Keep PRs focused — one logical change per PR
- All CI checks must pass before merge
- Security-sensitive paths (`src/cloudctl/providers/`, `src/cloudctl/guardrails.py`,
  `src/cloudctl/use_exports.py`, `.github/workflows/`) warrant extra review
- Include a **behavioural** test for new behaviour (a green suite alone has
  historically hidden broken credential injection)
- Update `CHANGELOG.md` for user-visible changes

## Reporting Security Issues

See [SECURITY.md](SECURITY.md). Do **not** open a public issue for vulnerabilities.

## Code Style

- Formatter: `black` (enforced in CI)
- Linter: `ruff` (enforced in CI)
- Types: `mypy`
