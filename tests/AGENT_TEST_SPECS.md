# Agent Test Specifications — PHASE 5A Template

## Overview

This document specifies the test requirements for each agent. Tests should be committed as part of each agent's feature branch and integrated in PHASE 5B.

**Target**: 450+ tests total, 90%+ coverage  
**Current baseline**: 581 existing tests (from main branch)

---

## Agent 1: Error Handling Tests

**Branch**: `feat/error-handling`  
**Module**: `src/cloudctl/errors.py`  
**Test File**: `tests/test_errors_agent1.py`

### Test Responsibilities

Comprehensive error handling for all error types including:

1. **Configuration Errors**
   - Missing orgs.yaml
   - Invalid YAML syntax
   - Missing required fields
   - Schema validation failures
   - File permission errors

2. **AWS Integration Errors**
   - Invalid AWS credentials
   - Expired SSO tokens
   - Invalid region
   - InvalidClientTokenId
   - AccessDenied
   - ThrottlingException
   - ServiceUnavailable

3. **Role Validation Errors**
   - Role not found for account
   - Invalid role name
   - User not authorized for role
   - Role has no permissions

4. **Context Management Errors**
   - No active context
   - Context file corrupted
   - Context expired
   - Stale context

5. **CLI/UX Errors**
   - Invalid argument combinations
   - Missing required arguments
   - Ambiguous input
   - User interruption (Ctrl+C)

### Test Targets

- **Test Count**: 80-100 tests
- **Coverage**: 95%+ of `src/cloudctl/errors.py` and error handling paths
- **Base Class**: `ErrorHandlingTestBase` from `test_infrastructure.py`

### Test Structure

```python
import pytest
from tests.test_infrastructure import ErrorHandlingTestBase
from cloudctl.exceptions import (
    CloudCtlError,
    ConfigError,
    AWSError,
    RoleValidationError,
    ContextError,
)

class TestErrorHandling(ErrorHandlingTestBase):
    """Error handling tests for Agent 1."""
    
    @pytest.mark.unit
    @pytest.mark.error_handling
    def test_config_error_message_format(self):
        """Test ConfigError message format."""
        # Your test implementation
        pass
    
    @pytest.mark.unit
    @pytest.mark.error_handling
    def test_aws_error_context_preservation(self):
        """Test AWSError preserves original exception context."""
        # Your test implementation
        pass
```

### Checklist

- [ ] All error classes have basic instantiation tests
- [ ] All error types have message validation tests
- [ ] Error inheritance chains are validated
- [ ] Error context/cause is preserved
- [ ] Error messages are user-friendly and actionable
- [ ] Graceful degradation paths are tested
- [ ] Error recovery suggestions work

---

## Agent 2: Config Encryption Tests

**Branch**: `feat/config-encryption`  
**Module**: `src/cloudctl/encryption.py` (new or enhanced)  
**Test File**: `tests/test_encryption_agent2.py`

### Test Responsibilities

Comprehensive encryption/decryption testing for sensitive config:

1. **Encryption Operations**
   - Encrypt plaintext config values
   - Deterministic or random IV handling
   - Key derivation/management
   - Algorithm validation (AES-256-GCM recommended)

2. **Decryption Operations**
   - Decrypt valid ciphertext
   - Handle corrupted ciphertext
   - Handle wrong key
   - Handle expired/rotated keys

3. **Config Storage**
   - Encrypt orgs.yaml sensitive fields (API keys, tokens)
   - Decrypt on config load
   - Preserve non-sensitive fields unencrypted
   - Handle mixed encrypted/unencrypted configs

4. **Key Management**
   - Generate secure keys
   - Store keys securely (system keyring if available)
   - Rotate keys
   - Handle missing keys gracefully

5. **Roundtrip Testing**
   - Plaintext → Encrypt → Decrypt → Original
   - Large configs (>10MB)
   - Special characters and unicode
   - Binary data

### Test Targets

- **Test Count**: 70-90 tests
- **Coverage**: 100% of `src/cloudctl/encryption.py`
- **Base Class**: `EncryptionTestBase` from `test_infrastructure.py`

### Test Structure

```python
import pytest
from tests.test_infrastructure import EncryptionTestBase

class TestConfigEncryption(EncryptionTestBase):
    """Config encryption tests for Agent 2."""
    
    @pytest.mark.unit
    @pytest.mark.encryption
    def test_encrypt_decrypt_roundtrip(self, encrypt_fn, decrypt_fn):
        """Test plaintext roundtrips through encrypt/decrypt."""
        plaintext = "sensitive-api-key-12345"
        self.test_roundtrip(encrypt_fn, decrypt_fn, plaintext)
    
    @pytest.mark.unit
    @pytest.mark.encryption
    def test_encryption_with_wrong_key(self, encrypt_fn, decrypt_fn):
        """Test decryption fails with wrong key."""
        # Your test implementation
        pass
```

### Checklist

- [ ] All encryption operations have roundtrip tests
- [ ] Key management paths are tested
- [ ] Decryption of corrupted data fails gracefully
- [ ] Wrong key detection works
- [ ] Large configs are handled efficiently
- [ ] Unicode and special characters work
- [ ] Performance is acceptable (encrypt/decrypt <1s)
- [ ] Backward compatibility with unencrypted configs

---

## Agent 3: List Roles Tests

**Branch**: `feat/list-roles`  
**Module**: `src/cloudctl/commands/list_roles.py` (new)  
**Test File**: `tests/test_list_roles_agent3.py`

### Test Responsibilities

Comprehensive role listing and validation testing:

1. **Role Listing**
   - List roles for AWS account
   - List roles for Azure subscription
   - List roles for GCP project
   - Filter by permissions
   - Pagination support
   - Caching of role lists

2. **Role Validation**
   - Exact role name matching
   - Case-insensitive matching
   - Substring/fuzzy matching
   - Typo suggestions (Levenshtein distance)
   - Max suggestions (limit to 3-5)

3. **User Interface**
   - Interactive role picker
   - Non-interactive mode (exit with error if ambiguous)
   - Formatted output (table, JSON, YAML)
   - Error messages with suggestions

4. **Integration**
   - Works with cmd_switch() flow
   - Works with pre-configured context
   - Works with no pre-configured context
   - Graceful fallback if SSO unavailable

### Test Targets

- **Test Count**: 60-80 tests
- **Coverage**: 90%+ of list_roles functionality
- **Base Class**: `RoleValidationTestBase` from `test_infrastructure.py`

### Test Structure

```python
import pytest
from tests.test_infrastructure import RoleValidationTestBase

class TestListRoles(RoleValidationTestBase):
    """List roles tests for Agent 3."""
    
    @pytest.mark.unit
    @pytest.mark.role_validation
    def test_exact_role_matching(self, validator, available_roles):
        """Test exact role name matching."""
        self.test_role_exact_match(validator, available_roles, "Admin")
    
    @pytest.mark.unit
    @pytest.mark.role_validation
    def test_case_insensitive_matching(self, validator):
        """Test case-insensitive role matching."""
        # Your test implementation
        pass
```

### Checklist

- [ ] All cloud providers have role listing tests
- [ ] Exact matching works for all role names
- [ ] Case-insensitive matching works
- [ ] Substring matching works
- [ ] Fuzzy matching generates good suggestions
- [ ] Empty role lists handled gracefully
- [ ] Large role lists (>100) work efficiently
- [ ] Pagination works end-to-end
- [ ] Caching doesn't cause stale data
- [ ] Integration with cmd_switch verified

---

## PHASE 5B: Integration Instructions

When your code is complete:

1. **Commit your tests to your branch:**
   ```bash
   git add tests/test_<agent_module>.py
   git commit -m "test(<module>): Add comprehensive tests for <feature>
   
   - <Test category 1>: N tests
   - <Test category 2>: N tests
   
   Total: N new tests, X% coverage
   
   Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
   ```

2. **Run your tests locally:**
   ```bash
   poetry run pytest tests/test_<agent_module>.py -v --cov=src/cloudctl/<module>
   ```

3. **Verify coverage:**
   - Target: 90%+ coverage
   - Check: `--cov-report=term-missing` to find gaps

4. **Create PR** with link to branch

5. **Agent 5 Integration** (PHASE 5B):
   - Merges all 4 feature branches
   - Runs full test suite: `pytest tests/ -v --cov`
   - Generates coverage report
   - Updates CI/CD if needed

---

## Test Data Factory

Use `TestDataFactory` from `test_infrastructure.py` for consistent test data:

```python
from tests.test_infrastructure import TestDataFactory

# Create test AWS objects
account = TestDataFactory.make_aws_account()
role = TestDataFactory.make_aws_role("Admin")
identity = TestDataFactory.make_sts_identity()

# Create test configs
config = TestDataFactory.make_orgs_config()
context = TestDataFactory.make_context_json()

# Create test skill data
request = TestDataFactory.make_skill_request()
response = TestDataFactory.make_skill_response()
```

---

## Available Fixtures

From `conftest.py`:

- `mock_home` — Hermetic home directory
- `mock_rich_console` — Console capture
- `mock_aws_sso_client` — Mocked SSO client
- `mock_aws_sts_client` — Mocked STS client
- `mock_boto3_session` — Mocked boto3 session
- `sample_orgs_yaml` — Valid orgs.yaml config
- `context_json_valid` — Valid context.json
- `sample_sso_cache` — Valid SSO cache entry

---

## Test Markers

```bash
# Mark your tests appropriately
@pytest.mark.unit              # No external dependencies
@pytest.mark.error_handling    # For Agent 1
@pytest.mark.encryption        # For Agent 2
@pytest.mark.role_validation   # For Agent 3
@pytest.mark.slow              # If test >1 second
@pytest.mark.aws               # If test uses AWS APIs
```

---

## Running Your Tests

```bash
# All your tests
pytest tests/test_<agent_module>.py -v --cov

# By marker
pytest tests/ -m error_handling -v
pytest tests/ -m encryption -v
pytest tests/ -m role_validation -v

# With coverage
pytest tests/test_<agent_module>.py -v --cov=src/cloudctl/<module> --cov-report=html
```

---

## Questions?

See `docs/TEST_INFRASTRUCTURE.md` for complete testing guide.

---

Generated for PHASE 5A (2026-05-27)
