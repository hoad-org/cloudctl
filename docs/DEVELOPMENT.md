# CloudCtl Development Guide

For contributors and developers working on CloudCtl itself.

## Repository Structure

```
cloudctl/
├── src/cloudctl/           # Main source code
│   ├── cli.py             # CLI entry point
│   ├── core.py            # Core functionality
│   ├── aws.py             # AWS integration
│   ├── config.py          # Configuration handling
│   ├── errors.py          # Error definitions
│   └── ...                # Other modules
├── tests/                 # Test suite
│   ├── test_*.py         # Unit tests
│   └── conftest.py       # Test fixtures
├── docs/                 # Documentation
│   ├── INSTALLATION.md
│   ├── CONFIGURATION.md
│   ├── COMMAND_REFERENCE.md
│   └── ...
├── pyproject.toml        # Package config
├── pytest.ini            # Test config
├── CHANGELOG.md          # Version history
└── README.md             # Project overview
```

## Development Setup

### Prerequisites

- Python 3.12
- git
- AWS CLI v2
- pip

### Install for Development

```bash
# Clone the repository
git clone https://github.com/BT-IT-Infrastructure-CloudOps/cloudctl.git
cd cloudctl

# Install in editable mode with dev dependencies
python3.12 -m pip install -e ".[dev]"

# Verify installation
python3.12 -m cloudctl --version
```

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/cloudctl

# Run specific test file
pytest tests/test_core.py

# Run with verbose output
pytest -v
```

## Code Style

CloudCtl uses:
- **Black** for code formatting (line length: 100)
- **Ruff** for linting
- **mypy** for type checking

### Format Code

```bash
# Format with Black
black src/ tests/

# Check linting
ruff check src/ tests/

# Fix linting issues
ruff check --fix src/ tests/
```

## Making Changes

### Before Starting

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Read the [CLAUDE.md](../CLAUDE.md) file for repo-specific guidelines

3. Check existing code patterns in `src/cloudctl/`

### Writing Code

**General Rules:**
- Follow PEP 8 style guide
- Use type hints
- Write docstrings for public functions
- Keep functions focused and testable
- Write tests for new functionality

**Example:**
```python
def cmd_example(org: str, account: str) -> dict[str, str]:
    """Example CloudCtl command handler.
    
    Args:
        org: Organization name
        account: AWS account ID
        
    Returns:
        Dictionary with operation result
    """
    # Implementation here
    return {"status": "success"}
```

### Writing Tests

**Test Structure:**
```python
def test_example_success():
    """Test example function succeeds with valid input."""
    result = cmd_example(org="bt-avm", account="235494790978")
    assert result["status"] == "success"


def test_example_invalid_account():
    """Test example function fails with invalid account."""
    with pytest.raises(ValueError):
        cmd_example(org="bt-avm", account="invalid")
```

## Version Management

CloudCtl uses semantic versioning: `MAJOR.MINOR.PATCH`

### Increment Version

1. **Update `pyproject.toml`:**
   ```toml
   [tool.poetry]
   version = "1.0.1"  # Increment as needed
   ```

2. **Update `src/cloudctl/_version.py`:**
   ```python
   __version__ = "1.0.1"
   ```

3. **Update CHANGELOG.md** with changes

4. **Commit:** `chore: bump version to 1.0.1`

5. **Tag:** `git tag v1.0.1`

6. **Push:** `git push --tags`

## Submission Guidelines

### Before Submitting a PR

- [ ] Code follows style guide (Black, Ruff)
- [ ] All tests pass (`pytest`)
- [ ] New code has tests (>80% coverage)
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] No credentials or secrets in code
- [ ] Type hints added to new functions

### PR Title Format

```
type: description

Examples:
- feat: add whoami command
- fix: resolve token refresh timeout
- docs: update error reference
- test: add comprehensive test suite
```

## CI/CD Pipeline

CloudCtl uses GitHub Actions for:
- **Lint checks** (Black, Ruff, mypy)
- **Unit tests** (pytest with coverage)
- **Security scanning** (bandit, pip-audit)
- **Integration tests** (AWS)

View pipeline: `.github/workflows/ci.yml`

## Deployment

### Build Package

```bash
python3.12 -m build
```

### Upload to PyPI

```bash
python3.12 -m twine upload dist/*
```

## Security Considerations

### No Credentials in Code

- Never hardcode AWS keys, tokens, or secrets
- Use environment variables for sensitive data
- All credential tests must use mocks

### Credential Handling

- Credentials handled internally only
- Never exported to environment
- Auto-cleanup on function exit
- Comprehensive audit logging

## Architecture Overview

### Command Flow

```
User Input
    ↓
CLI Parser (cli.py)
    ↓
Command Handler (cmd_*.py)
    ↓
Core Logic (core.py)
    ↓
AWS Integration (aws.py)
    ↓
Output → Audit Log
```

### Key Modules

| Module | Purpose |
|--------|---------|
| `cli.py` | CLI argument parsing, routing |
| `core.py` | Main business logic |
| `aws.py` | AWS SDK integration |
| `config.py` | Configuration loading |
| `errors.py` | Custom error types |

## Common Development Tasks

### Add a New Command

1. Create handler in appropriate module
2. Register in CLI parser (`cli.py`)
3. Add to `_DISPATCH` dict
4. Write tests (`tests/test_*.py`)
5. Update documentation
6. Update CHANGELOG.md

### Fix a Bug

1. Write failing test first
2. Fix the code
3. Verify test passes
4. Add regression test if needed
5. Update CHANGELOG.md

### Update Documentation

1. Edit relevant `.md` file
2. Verify formatting
3. Test links are correct
4. Commit with `docs:` prefix

## Troubleshooting Development

### Tests failing

```bash
# Run with verbose output
pytest -vv

# Run single test
pytest tests/test_core.py::test_specific

# Run with print statements
pytest -s
```

### Import errors

```bash
# Reinstall in editable mode
python3.12 -m pip install -e . --force-reinstall

# Check Python path
python3.12 -c "import cloudctl; print(cloudctl.__file__)"
```

### Type errors

```bash
# Run mypy
mypy src/cloudctl

# Check specific file
mypy src/cloudctl/core.py
```

## Resources

- [CHANGELOG.md](../CHANGELOG.md) — Version history and changes
- [CLAUDE.md](../CLAUDE.md) — Repo-specific development guidelines
- [GitHub Issues](https://github.com/BT-IT-Infrastructure-CloudOps/cloudctl/issues) — Bug reports and features
- [Pull Requests](https://github.com/BT-IT-Infrastructure-CloudOps/cloudctl/pulls) — Ongoing development

---

## Getting Help

- Check existing issues/PRs
- Read test examples for usage patterns
- Review CLAUDE.md for repo conventions
- Ask platform team in #cloudops Slack

---
