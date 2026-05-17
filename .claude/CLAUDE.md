# CloudCTL Development & Operations Guide

This file provides context and operational guidelines for working on the cloudctl repository.

## Quick Navigation

- **[Confluence Integration](#confluence-integration)** — Document cloud operations
- **[Repository Structure](#repository-structure)** — Where everything lives
- **[Multi-Cloud Operations](#multi-cloud-operations)** — AWS, GCP, Azure differences
- **[Testing Guide](#testing-guide)** — How to run and write tests
- **[Development Workflow](#development-workflow)** — Adding features and providers
- **[Troubleshooting](#troubleshooting)** — Common issues and solutions
- **[Performance & Optimization](#performance--optimization)** — Timeout settings, CLI response times

---

## Confluence Integration

This repository is configured for automatic documentation to Confluence.

**Target Space**: `Hoad-cloud-platforms`  
**Jira Project**: `HCP`  
**Instance**: darkmothcreative.atlassian.net

### When to Document

Use the Confluence skill to generate docs for:
- New API endpoints or backend changes
- Architecture decisions (ADR)
- Infrastructure changes or deployments
- Runbooks and operational guides
- Feature specifications
- Troubleshooting guides

### How Claude Should Use the Confluence Skill

**Always**:
1. Use the Confluence skill when user asks to document anything
2. Pass `repo_path="."` to automatically use this repo's configuration
3. Set `dry_run=False` only after user approval

**Example**:
```python
skill.document(
    task="Document the new payment API",
    repo_path=".",
    dry_run=False
)
```

The skill will automatically:
- Create/update pages in the `Hoad-cloud-platforms` space
- Link related issues in the `HCP` Jira project
- Validate all inputs and permissions
- Create tasks for undocumented APIs

---

## Repository Structure

```
aws-terraform-infra-cloudops-awsctl/
├── src/cloudctl/                       # Main Python package
│   ├── __init__.py                     # Package entry point
│   ├── __main__.py                     # CLI entry point (python -m cloudctl)
│   ├── main.py                         # main() function for setuptools
│   ├── cli.py                          # Command routing and argument parsing
│   ├── core.py                         # Core business logic
│   ├── config.py                       # Configuration loading (4-level hierarchy)
│   ├── context_manager.py              # Active context persistence (~/.config/cloudctl/context.json)
│   ├── schema.py                       # Configuration validation
│   ├── shell.py                        # Shell wrapper injection/removal
│   ├── interactive.py                  # Account/role/region selection pickers
│   ├── guardrails.py                   # Security gates (region, role validation)
│   ├── doctor.py                       # System health checks
│   ├── utils.py                        # Shared utilities
│   │
│   ├── aws.py                          # AWS CLI integration (SSO, STS, profiles)
│   ├── sso_cache.py                    # AWS SSO token cache parsing
│   ├── accounts.py                     # Account enumeration
│   ├── use_exports.py                  # AWS credential export (legacy)
│   │
│   ├── providers/                      # Cloud provider abstraction layer
│   │   ├── base.py                     # CloudProvider abstract base class
│   │   ├── aws.py                      # AWS provider implementation
│   │   ├── azure.py                    # Azure provider implementation
│   │   ├── gcp.py                      # GCP provider implementation
│   │   └── __init__.py                 # Provider factory
│   │
│   ├── wizard/                         # Interactive setup wizards
│   ├── commands/                       # Individual command implementations (mostly legacy)
│   ├── plugins/                        # Plugin framework (reserved for future use)
│   └── registry.py                     # Governance registry (immutable configuration)
│
├── tests/                              # Test suite (400+ tests)
│   ├── test_*.py                       # Unit tests
│   ├── integration/                    # End-to-end integration tests
│   ├── conftest.py                     # Pytest configuration and fixtures
│   └── [provider tests]                # Per-provider test modules
│
├── docs/                               # User-facing documentation
│   ├── ARCHITECTURE.md                 # Design patterns, Split-Plane model
│   ├── DEPLOYMENT.md                   # Installation and setup (NEW)
│   ├── MULTI_CLOUD.md                  # Cloud provider comparison (NEW)
│   ├── GCP.md                          # GCP-specific details
│   ├── adr/                            # Architecture Decision Records
│   └── wiki/                           # FedRAMP, security, compliance docs
│
├── .claude/                            # Claude Code configuration
│   └── CLAUDE.md                       # This file
│
├── install.sh                          # macOS / Linux / WSL installer
├── install.ps1                         # Windows PowerShell installer
├── uninstall.sh                        # macOS / Linux / WSL uninstaller
├── uninstall.ps1                       # Windows PowerShell uninstaller
│
├── Makefile                            # Build, test, deploy targets
├── pyproject.toml                      # Project metadata, dependencies
├── poetry.lock                         # Locked dependency versions
├── conftest.py                         # Root pytest configuration
│
└── README.md                           # Main user documentation
```

### Key Configuration Files

- **`~/.config/cloudctl/orgs.yaml`** — User org configuration (master config file)
- **`~/.config/cloudctl/context.json`** — Active context state (org, account, role, region)
- **`~/.aws/config`** — AWS profile configuration (managed by cloudctl during init)
- **`~/.aws/sso/cache/`** — AWS SSO token cache (read-only, managed by AWS CLI)
- **`~/.cloudctl/audit.log`** — Break-glass audit log (sensitive role access)

---

## Multi-Cloud Operations

CloudCTL supports three cloud providers with distinct authentication flows and models.

### AWS (Commercial and GovCloud)

**Provider Class**: `AwsProvider` (`src/cloudctl/providers/aws.py`)

**Concepts:**
- Account → AWS Account ID (12 digits)
- Role → IAM permission set (e.g., AdminAccess, ReadOnly)
- Region → AWS region (e.g., us-east-1, us-gov-west-1)

**Authentication Flow:**
1. `cloudctl login aws-org` → runs `aws sso login --sso-session <org>`
2. AWS CLI opens browser → IdP authentication
3. Credentials cached in `~/.aws/sso/cache/`
4. `cloudctl switch` → retrieves STS credentials from cache

**Configuration:**
```yaml
- name: bt-avm
  provider: aws
  partition: aws                    # or aws-us-gov, aws-cn
  sso_start_url: https://...        # AWS IAM Identity Center URL
  sso_region: us-east-1             # SSO region (NOT user region)
  allowed_regions: [...]            # Restrict available regions
  default_region: us-east-1
```

**Partitions:**
- `aws` — AWS Commercial (all regions)
- `aws-us-gov` — AWS GovCloud US (us-gov-east-1, us-gov-west-1 only)
- `aws-cn` — AWS China (cn-north-1, cn-northwest-1 only; **SSO not supported**)

**Environment Variables Exported:**
```bash
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_SESSION_TOKEN
AWS_PROFILE
```

**Special Cases:**
- AWS China (`aws-cn`) does not support IAM Identity Center — users must configure long-term IAM keys
- Partition-aware region filtering prevents invalid region selection
- GovCloud credentials are separate from commercial AWS

---

### Azure

**Provider Class**: `AzureProvider` (`src/cloudctl/providers/azure.py`)

**Concepts:**
- Account → Azure Subscription (UUID)
- Role → RBAC role (e.g., Contributor, Reader, Viewer)
- Region → Azure region (e.g., eastus, westeurope)

**Authentication Flow:**
1. `cloudctl login azure-org` → runs `az login`
2. Browser opens → Azure AD authentication
3. Token cached in `~/.azure/` (managed by Azure CLI)
4. `cloudctl switch` → retrieves access token

**Configuration:**
```yaml
- name: azure-prod
  provider: azure
  tenant_id: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx  # optional but recommended
  allowed_regions: [eastus, westeurope]             # optional
  default_region: eastus
  roles:                                             # optional; auto-discovers if omitted
    - Contributor
    - Reader
```

**Environment Variables Exported:**
```bash
AZURE_SUBSCRIPTION_ID
AZURE_TENANT_ID
ARM_SUBSCRIPTION_ID
ARM_TENANT_ID
ARM_ACCESS_TOKEN
```

**Special Cases:**
- If `tenant_id` is omitted, `az login` prompts for tenant selection
- RBAC roles are auto-discovered from live subscriptions (slower but accurate)
- If `roles` is configured statically, RBAC query is skipped (faster)
- Token expiry is read from `az account get-access-token` response

---

### GCP (Google Cloud Platform)

**Provider Class**: `GcpProvider` (`src/cloudctl/providers/gcp.py`)

**Concepts:**
- Account → GCP Project (project ID)
- Role → IAM role (e.g., roles/viewer, roles/editor, roles/owner)
- Region → GCP region (e.g., us-central1, europe-west1)

**Authentication Flow:**
1. `cloudctl login gcp-org` → runs `gcloud auth login`
2. Browser opens → Google account authentication
3. Token cached in `~/.config/gcloud/` (managed by gcloud)
4. Additionally runs `gcloud auth application-default login` for Terraform/SDKs
5. `cloudctl switch` → retrieves access token

**Configuration:**
```yaml
- name: gcp-prod
  provider: gcp
  default_project: my-project-id                    # required for default context
  allowed_regions: [us-central1, europe-west1]      # optional
  default_region: us-central1
  roles:                                             # optional
    - roles/viewer
    - roles/editor
```

**Environment Variables Exported:**
```bash
GOOGLE_CLOUD_PROJECT
CLOUDSDK_CORE_PROJECT
GCLOUD_PROJECT
GOOGLE_OAUTH_ACCESS_TOKEN
```

**Special Cases:**
- Non-interactive mode: if browser isn't available, `gcloud auth login --no-launch-browser` provides a URL
- Application Default Credentials (ADC) are set up separately via `gcloud auth application-default login`
- Token expiry is exactly 1 hour; gcloud auto-refreshes
- `GOOGLE_APPLICATION_CREDENTIALS` is set automatically for ADC support

---

## Testing Guide

CloudCTL has a comprehensive test suite with 430+ tests covering all providers and workflows.

### Running Tests

**Run all tests:**

```bash
make test
```

**Run specific test file:**

```bash
pytest tests/test_providers.py -v
```

**Run tests for specific provider:**

```bash
pytest tests/test_providers.py::test_aws_provider -v
pytest tests/test_providers.py::test_azure_provider -v
pytest tests/test_providers.py::test_gcp_provider -v
```

**Run with coverage report:**

```bash
make coverage
# Or manually:
pytest --cov=src/cloudctl --cov-report=term-missing tests/
```

**Run tests matching a pattern:**

```bash
pytest -k "test_switch" -v
```

### Test Organization

```
tests/
├── test_aws.py                    # AWS-specific tests
├── test_azure.py                  # Azure-specific tests
├── test_gcp.py                    # GCP-specific tests
├── test_cli.py                    # CLI routing and argument parsing
├── test_config.py                 # Configuration loading and validation
├── test_shell.py                  # Shell wrapper injection/removal
├── test_interactive.py            # Account/role/region pickers
├── test_guardrails.py             # Security gates
├── test_doctor.py                 # System health checks
├── test_providers.py              # Provider base class and common logic
├── conftest.py                    # Shared fixtures and mocking
└── integration/                   # End-to-end workflows
    ├── test_full_workflow_aws.py
    ├── test_full_workflow_azure.py
    └── test_full_workflow_gcp.py
```

### Writing Tests

**Mock cloud provider CLI calls:**

```python
import pytest
from unittest.mock import patch, MagicMock

def test_aws_list_accounts(monkeypatch):
    """Test AWS account enumeration."""
    mock_result = {
        "returncode": 0,
        "stdout": json.dumps([{"id": "111111111111", "name": "Production"}]),
        "stderr": ""
    }
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: MagicMock(
        returncode=mock_result["returncode"],
        stdout=mock_result["stdout"],
        stderr=mock_result["stderr"]
    ))
    
    provider = AwsProvider()
    accounts = provider.list_accounts(org_config, token)
    assert len(accounts) == 1
    assert accounts[0]["id"] == "111111111111"
```

**Test async provider methods (GCP/Azure):**

```python
import pytest

@pytest.mark.asyncio
async def test_gcp_login():
    """Test GCP authentication."""
    provider = GcpProvider()
    result = provider.login(gcp_org_config)
    assert result == 0
```

### Coverage Requirements

- Minimum coverage: **85%**
- Run `make coverage` to check
- Missing coverage in critical paths (auth, credentials, guardrails) must be addressed

---

## Development Workflow

### Adding a New Cloud Provider

1. **Create provider class** in `src/cloudctl/providers/newcloud.py`:
   ```python
   from .base import CloudProvider
   
   class NewCloudProvider(CloudProvider):
       def login(self, org): ...
       def load_token(self, org): ...
       def list_accounts(self, org, token): ...
       def list_roles(self, org, token, account_id): ...
       def get_credentials(self, org, account, role, region): ...
       def get_unsets(self): ...
       def logout(self, org): ...
   ```

2. **Register in provider factory** (`src/cloudctl/providers/__init__.py`):
   ```python
   from .newcloud import NewCloudProvider
   
   PROVIDERS = {
       "aws": AwsProvider,
       "azure": AzureProvider,
       "gcp": GcpProvider,
       "newcloud": NewCloudProvider,
   }
   ```

3. **Add tests** (`tests/test_newcloud.py`):
   - Test all abstract methods
   - Mock external CLI calls
   - Test error handling

4. **Update schema** (`src/cloudctl/schema.py`):
   - Add validation rules for new provider config
   - Document all config keys

5. **Run tests** and verify coverage ≥85%:
   ```bash
   make test
   make coverage
   ```

6. **Update documentation** (docs/MULTI_CLOUD.md):
   - Add provider concept mapping
   - Document environment variables
   - Include configuration example

### Adding a New CLI Command

1. **Add argument parser** in `src/cloudctl/cli.py`:
   ```python
   subparsers = parser.add_subparsers(dest="cmd")
   new_cmd = subparsers.add_parser("newcmd", help="...")
   new_cmd.add_argument("--option", help="...")
   ```

2. **Implement handler function**:
   ```python
   def cmd_newcmd(args):
       """Handle newcmd subcommand."""
       # Implementation
       return 0  # exit code
   ```

3. **Register in dispatcher**:
   ```python
   COMMANDS = {
       "newcmd": cmd_newcmd,
   }
   ```

4. **Write tests** (`tests/test_cli.py`):
   - Test argument parsing
   - Test happy path
   - Test error cases

5. **Run quality checks**:
   ```bash
   make check  # lint, format, type-check, tests
   ```

### Changing Configuration Schema

1. **Update schema definition** (`src/cloudctl/schema.py`):
   ```python
   ORG_SCHEMA = {
       "type": "object",
       "properties": {
           "new_field": {"type": "string"},
       }
   }
   ```

2. **Add migration** if backward compatibility needed

3. **Update example configs** (docs/ and README.md)

4. **Test validation** (`tests/test_schema.py`)

---

## Troubleshooting

### Common Issues

**Issue: `ImportError: No module named 'cloudctl'`**

**Solution:**
- Ensure cloudctl is installed: `pip list | grep cloudctl`
- If not installed, reinstall: `pip install /path/to/cloudctl.whl`
- If development mode: `pip install -e .` from repo root

**Issue: Shell wrapper not working (command not found)**

**Solution:**
- Re-run integration: `cloudctl init --shell-only`
- Check shell profile is sourcing the wrapper: `grep -n cloudctl ~/.zshrc`
- Restart shell: `exec zsh` or `exec bash`

**Issue: AWS SSO login fails with "user cancelled login"`**

**Solution:**
- Run `aws sso logout --sso-session <org>` to clear cached session
- Try `cloudctl login <org> --force` to force re-authentication
- Check SSO configuration: `cloudctl doctor`

**Issue: GCP credentials expired or `gcloud not found`**

**Solution:**
```bash
# Refresh GCP credentials
gcloud auth login
gcloud auth application-default login

# Re-login via cloudctl
cloudctl login <org> --force
```

**Issue: Azure CLI prompts for tenant every time**

**Solution:**
- Add `tenant_id` to orgs.yaml to pre-select tenant
- Or run: `az account set --subscription <subscription-id>`

**Issue: `NIST 800-53` or FedRAMP compliance error**

**Solution:**
- Check security controls in `docs/wiki/SECURITY_APPRAISAL.md`
- Verify environment: `cloudctl doctor --security`
- Review audit logs: `cat ~/.cloudctl/audit.log`

---

## Performance & Optimization

### CLI Response Times

CloudCTL is designed for low latency. Target response times:

- **`cloudctl switch`** (interactive picker): < 5 seconds
- **`cloudctl env`** (show context): < 100 ms
- **`cloudctl login`** (SSO): browser-dependent, typically 30-60 seconds
- **`cloudctl accounts`** (list subscriptions): < 3 seconds

### Timeout Settings

All external CLI calls have a **30-second timeout** to prevent hangs:

```python
# AWS CLI
result = subprocess.run([...], timeout=30)

# Azure CLI
result = subprocess.run([...], timeout=30)

# GCP CLI (gcloud)
result = subprocess.run([...], timeout=30)
```

If a command consistently times out:
1. Check network connectivity: `cloudctl doctor`
2. Check if the external CLI tool is responsive: `aws sts get-caller-identity`
3. Report with `--debug` flag: `cloudctl --debug switch`

### Token Caching

- **AWS**: Tokens cached in `~/.aws/sso/cache/` (12-hour TTL default)
- **Azure**: Tokens cached in `~/.azure/` (1-hour TTL)
- **GCP**: Tokens auto-refreshed by gcloud (1-hour TTL)

To force credential refresh:

```bash
cloudctl login <org> --force
```

### Region & Role Filtering

Region and role lists are computed once during `cloudctl switch` and cached in the context. Large account lists (>100 accounts) may take a few seconds to enumerate.

To speed up:
- Use `--account` and `--role` flags to skip interactive pickers: `cloudctl switch <org> --account 123 --role Admin`
- Configure `allowed_regions` to reduce filtering overhead

---

## Code Quality Standards

Before committing:

```bash
make check  # Runs all quality checks

# Or individually:
make lint        # ruff linter
make format      # black formatter
make type-check  # mypy type checking
make test        # pytest (>85% coverage)
```

**Git hooks**: The `.pre-commit-config.yaml` enforces these checks automatically.

---

## Useful Commands for Development

```bash
# Build and install locally
make build
pip install -e .

# Run all checks
make check

# Run with debug output
cloudctl --debug switch

# Export debug logs
export CLOUDCTL_DEBUG=1

# Test a specific cloud provider
pytest tests/test_providers.py::test_aws_provider -vv

# Generate coverage report
make coverage

# Run security scan
bandit -r src/

# Check dependencies for vulnerabilities
pip-audit
```

---

## References

- [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) — Detailed design patterns
- [docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md) — Installation guide
- [docs/MULTI_CLOUD.md](../docs/MULTI_CLOUD.md) — Provider-specific details
- [README.md](../README.md) — User-facing documentation
- [Makefile](../Makefile) — Build and test targets

