# Test Infrastructure - PHASE 5A Documentation

## Overview

This document describes the comprehensive test infrastructure created in **PHASE 5A** to support the concurrent development work of Agents 1-4.

**Current Status**: Infrastructure complete and ready for agent contributions  
**Test Target**: 450+ tests, 90%+ coverage across all modules

---

## Architecture

### Test Layers

```
┌─────────────────────────────────────────────────────┐
│ pytest.ini + CI/CD (.github/workflows/)             │ Config
├─────────────────────────────────────────────────────┤
│ tests/conftest.py (Enhanced with AWS mocking)       │ Fixtures
│ tests/integration/conftest.py (AWS integration)     │
├─────────────────────────────────────────────────────┤
│ tests/test_infrastructure.py (Base classes)         │ Utilities
├─────────────────────────────────────────────────────┤
│ tests/test_*.py (Unit tests)                        │ Tests
│ tests/integration/test_*.py (Integration tests)     │
└─────────────────────────────────────────────────────┘
```

### Test Categories

| Category | Location | Run Command | Notes |
|----------|----------|-------------|-------|
| **Unit** | `tests/test_*.py` | `pytest tests/ -m "not integration"` | No external deps |
| **Integration** | `tests/integration/` | `pytest tests/integration/` | Requires AWS mock/creds |
| **All** | `tests/` | `pytest tests/` | Full suite |

---

## Key Fixtures (in conftest.py)

### Environment & Home Directory

```python
@pytest.fixture(autouse=True)
def mock_home(tmp_path, monkeypatch):
    """Hermetic home directory for every test.
    
    Creates ~/.aws, ~/.cloudctl, ~/.config/cloudctl with proper structure.
    """
```

**Usage in tests:**
```python
def test_cloudctl_config(mock_home):
    config_dir = mock_home / ".config" / "cloudctl"
    assert config_dir.exists()
```

### AWS Mocking

```python
@pytest.fixture
def mock_aws_sso_client():
    """Mock boto3 SSO client with standard responses."""
    # list_accounts, list_roles_for_account pre-configured

@pytest.fixture
def mock_boto3_session(mock_aws_sso_client, mock_aws_sts_client, monkeypatch):
    """Full boto3 session mock."""
```

**Usage in tests:**
```python
def test_list_roles(mock_boto3_session):
    # boto3.Session now returns mock
    session = boto3.Session()
    sso = session.client('sso')
    # All calls are mocked
```

### Configuration

```python
@pytest.fixture
def sample_orgs_yaml(mock_home):
    """Valid orgs.yaml configuration in ~/.config/cloudctl/"""
    # Returns (file_path, config_dict)

@pytest.fixture
def context_json_valid(mock_home):
    """Valid context.json in ~/.cloudctl/"""
    # Returns (file_path, context_dict)

@pytest.fixture
def sample_sso_cache(mock_home):
    """Valid AWS SSO token cache entry."""
    # Returns (cache_file_path, cache_entry_dict)
```

### Console Capture

```python
@pytest.fixture
def mock_rich_console(monkeypatch):
    """Captures Rich console output without formatting."""
    
    # Usage:
    # cap.console.print("Hello")
    # assert "Hello" in cap.captured[0]
```

---

## Base Test Classes (test_infrastructure.py)

### For Agent 1: Error Handling Tests

```python
class ErrorHandlingTestBase(BaseTestCase):
    """Utilities for error testing."""
    
    def test_error_has_message(self, error_class, message):
        """Validate error message."""
    
    def test_error_inheritance(self, error_class, expected_parent):
        """Validate error inheritance chain."""
    
    def test_error_context_preservation(self, error_class, original_error):
        """Validate error context is preserved."""
```

**Example implementation (Agent 1):**
```python
import pytest
from tests.test_infrastructure import ErrorHandlingTestBase
from cloudctl.exceptions import ConfigError

class TestErrorHandling(ErrorHandlingTestBase):
    @pytest.mark.unit
    @pytest.mark.error_handling
    def test_config_error_message(self):
        self.test_error_has_message(ConfigError, "Config not found")
    
    @pytest.mark.unit
    @pytest.mark.error_handling
    def test_config_error_inheritance(self):
        self.test_error_inheritance(ConfigError, Exception)
```

### For Agent 2: Encryption Tests

```python
class EncryptionTestBase(BaseTestCase):
    """Utilities for encryption testing."""
    
    def test_roundtrip(self, encrypt_fn, decrypt_fn, plaintext):
        """Test encrypt->decrypt preserves plaintext."""
    
    def test_encryption_deterministic(self, encrypt_fn, plaintext):
        """Test encryption consistency (or randomness)."""
    
    def test_encryption_key_sensitivity(self, encrypt_fn, plaintext, key1, key2):
        """Test different keys produce different ciphertexts."""
```

**Example implementation (Agent 2):**
```python
from tests.test_infrastructure import EncryptionTestBase

class TestConfigEncryption(EncryptionTestBase):
    @pytest.mark.unit
    @pytest.mark.encryption
    def test_config_encryption_roundtrip(self, encrypt_config, decrypt_config):
        plaintext = "my-secret-api-key"
        self.test_roundtrip(encrypt_config, decrypt_config, plaintext)
```

### For Agent 3: Role Validation Tests

```python
class RoleValidationTestBase(BaseTestCase):
    """Utilities for role validation testing."""
    
    def test_role_exact_match(self, validator, available_roles, test_role):
        """Test exact role matching."""
    
    def test_role_case_insensitive(self, validator, available_roles):
        """Test case-insensitive matching."""
    
    def test_role_suggestions(self, validator, available_roles, typo_role):
        """Test suggestion generation for typos."""
```

**Example implementation (Agent 3):**
```python
from tests.test_infrastructure import RoleValidationTestBase

class TestRoleValidation(RoleValidationTestBase):
    @pytest.mark.unit
    @pytest.mark.role_validation
    def test_admin_role_exact_match(self, mock_aws_sso_client):
        available_roles = [
            {"roleName": "Admin"},
            {"roleName": "Developer"},
        ]
        self.test_role_exact_match(validator, available_roles, "Admin")
```

---

## Test Data Factory (test_infrastructure.py)

Standardized test data creation:

```python
from tests.test_infrastructure import TestDataFactory

# Create test data consistently
account = TestDataFactory.make_aws_account("123456789012", "Prod")
role = TestDataFactory.make_aws_role("Admin", "123456789012")
identity = TestDataFactory.make_sts_identity()
config = TestDataFactory.make_orgs_config()
context = TestDataFactory.make_context_json()
```

---

## Running Tests

### All Unit Tests (Default)
```bash
# Fast, no external dependencies
pytest tests/ -m "not integration" -v

# With coverage
pytest tests/ -m "not integration" -v --cov=src/cloudctl --cov-report=html
```

### All Integration Tests
```bash
# Requires AWS mock (moto) or real credentials
pytest tests/integration/ -v

# With moto (mocked AWS)
pytest tests/integration/ -v -k "not requires_sso"
```

### Specific Test Class/Function
```bash
# Single test
pytest tests/test_cli.py::TestCliDispatch::test_switch_command -v

# Test module
pytest tests/test_cli.py -v

# Tests matching marker
pytest tests/ -m "error_handling" -v
pytest tests/ -m "encryption" -v
pytest tests/ -m "role_validation" -v
```

### Coverage Report
```bash
# Generate HTML coverage report
pytest tests/ -m "not integration" --cov=src/cloudctl --cov-report=html

# View report
open htmlcov/index.html
```

---

## Test Markers (pytest.ini)

Available markers for categorizing tests:

```bash
# Run by marker
pytest -m unit           # Unit tests only
pytest -m integration    # Integration tests only
pytest -m error_handling # Agent 1 error tests
pytest -m encryption     # Agent 2 encryption tests
pytest -m role_validation # Agent 3 role tests
```

---

## CI/CD Integration

### Manual Run
```bash
# Trigger comprehensive test suite
gh workflow run test-comprehensive.yml
```

### Automatic Triggers
- **Push to main**: Runs full test suite
- **Pull requests**: Runs unit tests (integration conditional)
- **Daily (2 AM UTC)**: Full test suite with coverage

### Coverage Reporting
- Codecov integration enabled
- Coverage comment on PRs
- Minimum: 90% coverage required to pass

---

## PHASE 5B: Integration Checklist

When Agents 1-4 complete their code:

- [ ] Merge feat/error-handling (Agent 1)
- [ ] Merge feat/config-encryption (Agent 2)
- [ ] Merge feat/list-roles (Agent 3)
- [ ] Run full test suite: `pytest tests/ -v --cov`
- [ ] Verify coverage ≥90%
- [ ] Verify 450+ tests passing
- [ ] Verify CI/CD pipeline operational
- [ ] Generate coverage report

---

## Troubleshooting

### Import Errors
```bash
# Ensure dependencies installed
poetry install --with dev

# Check Python path
python -c "import cloudctl; print(cloudctl.__file__)"
```

### AWS Mock Not Working
```bash
# Verify moto installed
pip list | grep moto

# Install if missing
pip install moto
```

### Coverage Below Target
```bash
# Find missing coverage
pytest tests/ --cov=src/cloudctl --cov-report=term-missing

# Focus on low-coverage modules
pytest tests/ --cov=src/cloudctl/errors --cov-report=term-missing
```

---

## Reference

- **Base Classes**: `tests/test_infrastructure.py`
- **Fixtures**: `tests/conftest.py`, `tests/integration/conftest.py`
- **Configuration**: `pytest.ini`
- **CI/CD**: `.github/workflows/test-comprehensive.yml`
- **This Guide**: `docs/TEST_INFRASTRUCTURE.md`

---

Generated as part of PHASE 5A (2026-05-27)
