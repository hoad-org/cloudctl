## Summary

<!-- What does this PR do? Why? -->

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Security fix
- [ ] Dependency update
- [ ] Documentation / tooling

## Testing

- [ ] `poetry run pytest` passes locally
- [ ] `poetry run ruff check . && poetry run black --check .` passes
- [ ] `poetry run bandit -r src/ -ll` passes
- [ ] Manually tested against a real cloud account (if applicable)

## Security Checklist

_(complete if this PR touches credential handling, shell export, or provider code)_

- [ ] No credentials or tokens introduced
- [ ] Shell-exported values use `shlex.quote()`
- [ ] No new file writes without explicit permissions
- [ ] Audit log behaviour unchanged (or intentionally changed with justification)

## Notes for Reviewers

<!-- Anything that needs extra attention or context -->
