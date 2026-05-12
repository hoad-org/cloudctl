# Contributing to Hoad Cloud Platform

## Code Quality Standards

- **Tests:** Minimum 85% coverage required
- **Linting:** `ruff` (no warnings)
- **Formatting:** `black` (auto-formatted)
- **Type Checking:** `mypy --strict` (for Python)

Run locally: `make check`

## Before Submitting a PR

1. Run `make test` — all tests pass
2. Run `make check` — linting, formatting, types pass
3. Verify coverage: `make coverage` (must be ≥85%)
4. Keep commits atomic and descriptive

## Commit Message Format

```
<type>: <description>

<optional body>

<optional footer>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`

Example:
```
feat: add branch protection API support

Implements GitHub API integration for managing branch protection
rules across multiple repositories.
```

## PR Process

1. Create branch from `main`
2. Make changes, ensure tests pass
3. Open PR with clear description
4. Address review feedback
5. Maintainer merges when approved

## Questions?

Open an issue or discussion in the repository.
