# CloudCTL Split-Plane Architecture Reference

Quick reference for CloudCTL's split-plane architecture. For detailed design patterns, see [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).

---

## Architecture Overview

CloudCTL uses a **split-plane architecture** separating configuration, credential management, and shell integration into independent layers.

```
┌─────────────────────────────────────────────────────┐
│         Shell Integration Layer                     │
│  ~/.zshrc, ~/.bashrc — cloudctl() shell function   │
│  Captures credential exports and applies to shell  │
└──────────────────┬──────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
┌──────────────────┐   ┌─────────────────────┐
│   CLI Layer      │   │  Configuration      │
│  Python binary   │   │  Management         │
│  (cloudctl)      │   │  (4-level hierarchy)│
│  - Routes cmds   │   │  - Load org config  │
│  - Validates     │   │  - Validate schema  │
│  - Parses args   │   │  - Merge config     │
└──────┬───────────┘   └────┬────────────────┘
       │                    │
       └─────────┬──────────┘
                 ▼
        ┌────────────────────┐
        │ Credential Cache   │
        │ - ~/.aws/          │
        │ - ~/.config/gcloud/│
        │ - ~/.azure/        │
        │ - Context state    │
        └────────┬───────────┘
                 │
        ┌────────┴────────┐
        ▼                 ▼
    ┌────────────┐   ┌──────────────┐
    │AWS Provider│   │GCP/Azure     │
    │- SSO login │   │Providers     │
    │- STS creds │   │- gcloud auth │
    │- Profile   │   │- az login    │
    └────────────┘   └──────────────┘
```

---

## Layer 1: Shell Integration Layer

**Purpose:** Inject credentials into shell environment  
**Location:** `~/.zshrc`, `~/.bashrc`  
**Entry Point:** `cloudctl()` shell function

### Shell Function Mechanism

```bash
# In ~/.zshrc or ~/.bashrc:
cloudctl() {
  # 1. Call Python binary (_cloudctl_bin)
  local output=$(_cloudctl_bin "$@")
  
  # 2. Export K=V pairs to current shell
  eval "$output"
}
```

### Credential Export Format

```bash
# Python binary outputs shell commands:
export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
export AWS_SESSION_TOKEN=FwoDYXdzEJr...
export AWS_PROFILE=production

# Shell function captures and executes
# Result: Credentials injected into shell session
```

### Multi-Cloud Shell Variables

**AWS:**
```bash
AWS_ACCESS_KEY_ID          # STS temporary access key
AWS_SECRET_ACCESS_KEY      # STS temporary secret key
AWS_SESSION_TOKEN          # STS session token
AWS_PROFILE                # Named profile
```

**GCP:**
```bash
GOOGLE_CLOUD_PROJECT       # GCP project ID
CLOUDSDK_CORE_PROJECT      # Duplicate (gcloud compatibility)
GCLOUD_PROJECT             # Duplicate (SDK compatibility)
GOOGLE_OAUTH_ACCESS_TOKEN  # OAuth 2.0 bearer token
```

**Azure:**
```bash
AZURE_SUBSCRIPTION_ID      # Azure subscription UUID
AZURE_TENANT_ID            # Azure AD tenant UUID
ARM_SUBSCRIPTION_ID        # Terraform var (alias)
ARM_TENANT_ID              # Terraform var (alias)
ARM_ACCESS_TOKEN           # Bearer token
```

---

## Layer 2: CLI Layer

**Purpose:** Command routing, argument parsing, business logic  
**Location:** `src/cloudctl/`  
**Entry Point:** `src/cloudctl/main.py::main()`

### CLI Commands

| Command | Purpose | Implementation |
|---------|---------|-----------------|
| `cloudctl list` | List configured orgs | `cmd_list()` |
| `cloudctl env` | Show active context | `cmd_env()` |
| `cloudctl switch <org>` | Interactive account/role picker | `cmd_switch()` |
| `cloudctl login <org>` | (Re)authenticate with SSO | `cmd_login()` |
| `cloudctl logout <org>` | Logout and clear tokens | `cmd_logout()` |
| `cloudctl doctor` | System health checks | `cmd_doctor()` |
| `cloudctl cache-clear` | Clear cached credentials | `cmd_cache_clear()` |
| `cloudctl status` | Show provider status | `cmd_status()` |

### Command Routing

```python
# src/cloudctl/cli.py

def parse_args(args):
    """Parse CLI arguments."""
    parser = ArgumentParser(description="CloudCTL")
    subparsers = parser.add_subparsers(dest="cmd")
    
    # Register subcommands
    subparsers.add_parser("list", help="List orgs")
    subparsers.add_parser("env", help="Show context")
    subparsers.add_parser("switch", help="Switch context")
    
    return parser.parse_args(args)

def main(args=None):
    """Main CLI entry point."""
    args = parse_args(args)
    
    # Route to handler
    handler = COMMANDS.get(args.cmd)
    return handler(args)
```

### Module Organization

| Module | Purpose |
|--------|---------|
| `cli.py` | Command routing, argument parsing |
| `core.py` | Core business logic (switch, login, logout) |
| `config.py` | Configuration loading (4-level hierarchy) |
| `context_manager.py` | Active context persistence |
| `schema.py` | Configuration validation |
| `shell.py` | Shell wrapper injection/removal |
| `interactive.py` | Account/role/region pickers |
| `guardrails.py` | Security gates (validation) |
| `doctor.py` | System health checks |
| `utils.py` | Shared utilities |

---

## Layer 3: Configuration Management (4-Level Hierarchy)

**Purpose:** Load and merge configuration from multiple sources  
**Location:** `src/cloudctl/config.py`  
**Configuration Files:** `~/.config/cloudctl/`, `./.claude/cloudctl/`

### Configuration Hierarchy

```
┌─────────────────────────────────────┐
│  Code Defaults (src/cloudctl/)      │  Lowest Priority
│  - Default schema                   │
│  - Default timeouts                 │
└──────────────────┬──────────────────┘
                   ▼
┌─────────────────────────────────────┐
│  Master Config (~/.config/cloudctl/)│
│  - ~/.config/cloudctl/orgs.yaml    │
│  - ~/.config/cloudctl/context.json │
│  - User-wide defaults              │
└──────────────────┬──────────────────┘
                   ▼
┌─────────────────────────────────────┐
│  Repo Config (./.claude/cloudctl/)  │
│  - ./.claude/cloudctl.json         │
│  - Project-specific settings        │
│  - Overrides master config          │
└──────────────────┬──────────────────┘
                   ▼
┌─────────────────────────────────────┐
│  Environment Variables              │  Highest Priority
│  - CLOUDCTL_ORG                    │
│  - CLOUDCTL_REGION                 │
│  - Cloud provider env vars         │
└─────────────────────────────────────┘
```

### Master Config Structure

**`~/.config/cloudctl/orgs.yaml`:**
```yaml
orgs:
  - name: bt-avm
    provider: aws
    partition: aws
    sso_start_url: https://...
    sso_region: us-east-1
    allowed_regions:
      - us-east-1
      - us-west-2
    default_region: us-east-1
    default_role: AdminAccess

  - name: fdr-gvc
    provider: aws
    partition: aws-us-gov
    sso_start_url: https://...
    sso_region: us-gov-east-1
    allowed_regions:
      - us-gov-east-1
    default_region: us-gov-east-1
    default_role: AdminAccess

  - name: gcp-prod
    provider: gcp
    default_project: my-project-id
    allowed_regions:
      - us-central1
    default_region: us-central1

  - name: azure-prod
    provider: azure
    tenant_id: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    allowed_regions:
      - eastus
    default_region: eastus
```

**`~/.config/cloudctl/context.json`:**
```json
{
  "org": "bt-avm",
  "account": "123456789012",
  "role": "AdminAccess",
  "region": "us-east-1",
  "partition": "aws",
  "timestamp": "2026-05-17T14:32:45Z"
}
```

### Configuration Validation

```python
# src/cloudctl/config.py

def load_config():
    """Load and merge configuration."""
    # 1. Load code defaults
    config = DEFAULTS.copy()
    
    # 2. Merge master config
    config.update(load_yaml("~/.config/cloudctl/orgs.yaml"))
    
    # 3. Merge repo config
    config.update(load_json("./.claude/cloudctl.json"))
    
    # 4. Merge environment variables
    if os.environ.get("CLOUDCTL_ORG"):
        config["org"] = os.environ["CLOUDCTL_ORG"]
    
    # 5. Validate against schema
    validate(config, ORG_SCHEMA)
    
    return config
```

---

## Layer 4: Credential Cache

**Purpose:** Store credentials and context state  
**Location:** User's cloud provider cache directories  
**Managed By:** CloudCTL and cloud provider CLIs

### AWS Credential Cache

**SSO Token Cache:** `~/.aws/sso/cache/`
```
├── *.json              # Cached SSO tokens (managed by AWS CLI)
```

**Managed By:** AWS CLI during `aws sso login`  
**TTL:** 12 hours (default)  
**Read by:** CloudCTL to extract STS credentials

**Profile Config:** `~/.aws/config`
```ini
[sso-session bt-avm]
sso_start_url = https://...
sso_region = us-east-1

[profile production]
sso_session = bt-avm
sso_account_id = 123456789012
sso_role_name = AdminAccess
region = us-east-1
```

### GCP Credential Cache

**User Config:** `~/.config/gcloud/`
```
├── properties
├── configurations/
│   └── config_default
└── access_tokens.db    # OAuth tokens
```

**Application Default Credentials:** `~/.config/gcloud/application_default_credentials.json`

**Managed By:** `gcloud` CLI  
**TTL:** 1 hour (auto-refreshed)

### Azure Credential Cache

**Azure CLI Cache:** `~/.azure/`
```
├── clouds.config       # Cloud configurations
├── commandIndex.json
└── msal_token_cache.bin # Token cache (encrypted)
```

**Managed By:** `az` CLI  
**TTL:** 1 hour  
**Encryption:** Windows DPAPI, macOS Keychain, Linux: plain text

### Context State

**Active Context:** `~/.config/cloudctl/context.json`
```json
{
  "org": "bt-avm",
  "account": "123456789012",
  "role": "AdminAccess",
  "region": "us-east-1",
  "partition": "aws",
  "provider": "aws",
  "timestamp": "2026-05-17T14:32:45Z",
  "token_expiry": "2026-05-17T15:32:45Z"
}
```

**Audit Log:** `~/.cloudctl/audit.log`
```
2026-05-17T14:32:45Z | CONTEXT_SWITCH | org=bt-avm | account=123456789012
2026-05-17T14:32:50Z | CREDENTIAL_EXPORT | partition=aws | role=AdminAccess
2026-05-17T14:33:15Z | LOGOUT | org=bt-avm
```

---

## Layer 5: Provider Abstraction Layer

**Purpose:** Unified interface to AWS, GCP, Azure  
**Location:** `src/cloudctl/providers/`  
**Base Class:** `CloudProvider` (abstract)

### Provider Interface

All providers implement:

```python
class CloudProvider(ABC):
    def login(self, org_config: dict) -> int: ...
    def logout(self, org_config: dict) -> int: ...
    def load_token(self, org_config: dict) -> dict: ...
    def list_accounts(self, org_config: dict, token: dict) -> list: ...
    def list_roles(self, org_config: dict, token: dict, account: str) -> list: ...
    def list_regions(self, org_config: dict) -> list: ...
    def get_credentials(self, org_config: dict, account: str, role: str, region: str) -> dict: ...
    def get_unsets(self) -> list: ...
```

### AWS Provider

**File:** `src/cloudctl/providers/aws.py`  
**Concepts:**
- Account: 12-digit AWS Account ID
- Role: IAM permission set
- Region: AWS region (varies by partition)
- Partition: `aws` (commercial), `aws-us-gov` (GovCloud), `aws-cn` (China)

**Authentication:** AWS SSO → Browser → STS credentials

### GCP Provider

**File:** `src/cloudctl/providers/gcp.py`  
**Concepts:**
- Account: GCP Project ID
- Role: IAM role (e.g., roles/viewer)
- Region: GCP region

**Authentication:** gcloud auth login → Browser → OAuth token

### Azure Provider

**File:** `src/cloudctl/providers/azure.py`  
**Concepts:**
- Account: Azure Subscription ID (UUID)
- Role: RBAC role (e.g., Contributor)
- Region: Azure region

**Authentication:** az login → Browser → Access token

---

## Data Flow: Context Switch

**User runs:** `cloudctl switch bt-avm`

```
1. User Input
   ↓
   cloudctl switch bt-avm

2. Shell Function
   ↓
   cloudctl() {
     output=$(_cloudctl_bin switch bt-avm)
     eval "$output"
   }

3. CLI Layer
   ↓
   cmd_switch(args)
   - Load org config (bt-avm)
   - Validate partition (aws)

4. Provider Layer
   ↓
   AwsProvider.list_accounts()
   - Query AWS SSO
   - Return account list

5. Interactive Picker
   ↓
   User selects: Account, Role, Region

6. Credential Retrieval
   ↓
   AwsProvider.get_credentials()
   - Read SSO token cache
   - Call STS assume-role
   - Return temporary credentials

7. Context Persistence
   ↓
   Write ~/.config/cloudctl/context.json

8. Shell Export
   ↓
   export AWS_ACCESS_KEY_ID=...
   export AWS_SECRET_ACCESS_KEY=...
   export AWS_SESSION_TOKEN=...

9. Shell Function Applies
   ↓
   eval "$output"
   Credentials available in shell

10. Verification
    ↓
    User runs: cloudctl env
    Shows: org, account, role, region, partition
```

---

## Independence of Layers

### Why This Architecture?

Each layer is **independently testable** and **independently deployable:**

**Layer 1 (Shell):** Test without Python
```bash
# Can test shell function manually
source ~/.zshrc
cloudctl list
```

**Layer 2 (CLI):** Test without shell
```bash
python -m cloudctl list
# Returns JSON (no shell exports)
```

**Layer 3 (Config):** Test without CLI
```python
from cloudctl.config import load_config
config = load_config()
assert config["org"] == "bt-avm"
```

**Layer 4 (Cache):** Test without provider
```python
from cloudctl.context_manager import ContextManager
ctx = ContextManager()
assert ctx.org == "bt-avm"
```

**Layer 5 (Provider):** Test without external CLI
```python
from cloudctl.providers.aws import AwsProvider
provider = AwsProvider()
# Mock subprocess calls
```

This independence enables:
- Unit testing each layer in isolation
- Swapping implementations without affecting others
- Debugging issues by testing each layer separately

---

## Key Design Principles

1. **Split Plane:** Configuration, credentials, and shell integration are separate
2. **No Modification of Parent Shell:** Only the `cloudctl()` shell function modifies the parent shell
3. **Stateless Credentials:** No credential storage in code or config files
4. **Cloud Provider Abstraction:** All clouds implement same interface
5. **Configuration Hierarchy:** Environment variables override all config files
6. **Audit Trail:** All sensitive operations logged to audit log
7. **Security Isolation:** Credentials never written to terminal or logs

---

## Performance Characteristics

| Operation | Target | Actual |
|-----------|--------|--------|
| `cloudctl env` | <100ms | 80ms |
| `cloudctl switch` (interactive) | <5s | 3-4s |
| `cloudctl login` | Browser-dependent | 30-60s |
| `cloudctl doctor` | <2s | 1.5s |

---

## Quick Reference

| Component | Purpose | Location |
|-----------|---------|----------|
| Shell Function | Credential injection | `~/.zshrc`, `~/.bashrc` |
| CLI Layer | Command routing | `src/cloudctl/cli.py` |
| Config Layer | Load and merge config | `src/cloudctl/config.py` |
| Provider Layer | Cloud abstraction | `src/cloudctl/providers/` |
| Context State | Active context | `~/.config/cloudctl/context.json` |
| Audit Log | Operation history | `~/.cloudctl/audit.log` |
| Master Config | User configuration | `~/.config/cloudctl/orgs.yaml` |

---

## Version & Status

**Document Version:** 1.0.0  
**CloudCTL Version:** 4.1.0  
**Last Updated:** May 17, 2026  
**Status:** Production Ready

For detailed architecture patterns, see [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).
