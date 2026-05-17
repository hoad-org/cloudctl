# Multi-Cloud Operations Guide

CloudCTL manages identity and context across three cloud providers: AWS (commercial and GovCloud), Microsoft Azure, and Google Cloud Platform. This guide explains the differences and how to work with each.

---

## Overview: Conceptual Mapping

CloudCTL abstracts cloud-specific concepts into a unified model:

| CloudCTL Concept | AWS | Azure | GCP |
|---|---|---|---|
| **Account** | AWS Account (12-digit ID) | Subscription (UUID) | Project (ID) |
| **Role** | IAM permission set (e.g., AdminAccess) | RBAC role (e.g., Contributor) | IAM role (e.g., roles/viewer) |
| **Region** | AWS region (e.g., us-east-1) | Azure region (e.g., eastus) | GCP region (e.g., us-central1) |
| **Authentication** | AWS IAM Identity Center (SSO) | Azure CLI (az) | Google Cloud SDK (gcloud) |
| **Token Location** | `~/.aws/sso/cache/` | `~/.azure/` | `~/.config/gcloud/` |
| **Token Expiry** | 12 hours (configurable) | 1 hour | 1 hour (auto-refresh) |

---

## AWS (Commercial & GovCloud)

### Quick Start

```bash
# Add AWS organization
cloudctl org add

# Authenticate
cloudctl login bt-avm

# Switch context
cloudctl switch bt-avm

# View active context
cloudctl env
```

### Architecture: IAM Identity Center (SSO)

AWS uses **IAM Identity Center** for authentication and authorization.

**Flow:**

```
1. cloudctl login <org>
   ↓
2. Runs: aws sso login --sso-session <org>
   ↓
3. Browser opens → IdP authentication (Okta, Azure AD, etc.)
   ↓
4. Token cached in ~/.aws/sso/cache/
   ↓
5. cloudctl switch <org>
   ↓
6. Retrieves STS credentials for selected account/role
   ↓
7. Exports: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN
```

### Partitions: AWS, GovCloud, China

AWS operates across three **partitions** (isolated AWS clouds):

#### AWS Commercial (`aws`)

**Regions:** All commercial AWS regions (us-east-1, eu-west-1, ap-southeast-1, etc.)

**SSO Configuration:**
```yaml
- name: bt-avm
  provider: aws
  partition: aws                    # optional; defaults to aws
  sso_start_url: https://d-xxxxxxxxxx.awsapps.com/start
  sso_region: us-east-1
  allowed_regions: [us-east-1, us-west-2, eu-west-1]
```

**Service Endpoints:** `*.amazonaws.com`

#### AWS GovCloud (`aws-us-gov`)

**Regions:** US government regions only
- `us-gov-east-1`
- `us-gov-west-1`

**Isolation Level:** Physically isolated AWS infrastructure for FedRAMP compliance

**SSO Configuration:**
```yaml
- name: fdr-gvc
  provider: aws
  partition: aws-us-gov
  sso_start_url: https://d-yyyyyyyyyy.awsapps-us-gov.com/start
  sso_region: us-gov-west-1
  allowed_regions: [us-gov-east-1, us-gov-west-1]
```

**Service Endpoints:** `*.us-gov-aws.amazonaws.com`

**Important:**
- GovCloud credentials **cannot** access commercial AWS resources
- Commercial credentials **cannot** access GovCloud resources
- Separate SSO instances are required for each partition
- CloudCTL enforces partition boundaries (region picker validates)

#### AWS China (`aws-cn`)

**Regions:** China regions only
- `cn-north-1`
- `cn-northwest-1`

**Isolation Level:** Fully isolated AWS infrastructure operated by 21Vianet

**Authentication:** **IAM Identity Center is NOT supported in China**

**Configuration:**
```yaml
- name: china-ops
  provider: aws
  partition: aws-cn
  # No sso_start_url or sso_region — not applicable
```

**Setup Workaround:**

Since SSO isn't supported, use long-term IAM access keys:

```bash
# Manually set credentials
export AWS_ACCESS_KEY_ID=<your-key>
export AWS_SECRET_ACCESS_KEY=<your-secret>
export AWS_DEFAULT_REGION=cn-north-1

# Test connectivity
aws sts get-caller-identity --region cn-north-1
```

**Service Endpoints:** `*.amazonaws.com.cn`

---

### Region Constraints

CloudCTL validates region selection against the partition:

```bash
# ✅ Valid: us-east-1 in commercial AWS
cloudctl switch bt-avm --region us-east-1

# ✅ Valid: us-gov-west-1 in GovCloud
cloudctl switch fdr-gvc --region us-gov-west-1

# ❌ Invalid: us-east-1 in GovCloud (partition mismatch)
cloudctl switch fdr-gvc --region us-east-1
# Error: Region us-east-1 not in partition aws-us-gov
```

### Permission Sets vs IAM Roles

AWS IAM Identity Center uses **permission sets** (not traditional IAM roles):

```bash
# View available permission sets for an account
cloudctl accounts bt-avm

# Select a permission set
cloudctl switch bt-avm
# Picker: Account? [select one]
#         Permission Set? [select one] ← permission sets, not roles
```

**Note:** Permission sets are federated through SSO. They are not the same as IAM roles.

### Credential Expiry & Refresh

**Default Token TTL:** 12 hours (configured in IAM Identity Center)

**Monitoring Expiry:**

```bash
# Show active context with expiry countdown
cloudctl env
# Output:
# Org: bt-avm
# Account: 111111111111
# Role: AdminAccess
# Region: us-east-1
# Expires: 2024-03-15 14:30:00 (in 10 hours)
```

**Refresh Before Expiry:**

```bash
# Automatic refresh (watch for expiry)
cloudctl watch --threshold 900  # Refresh when <15 min remain

# Manual refresh
cloudctl login bt-avm --force

# Or in background
cloudctl watch bt-avm &
```

### Environment Variables

When you switch to an AWS context, these variables are exported:

```bash
export AWS_ACCESS_KEY_ID=<temporary-key>
export AWS_SECRET_ACCESS_KEY=<temporary-secret>
export AWS_SESSION_TOKEN=<session-token>
export AWS_PROFILE=<profile-name>
```

---

## Azure

### Quick Start

```bash
# Add Azure organization
cloudctl org add

# Authenticate (opens browser for Azure AD login)
cloudctl login azure-prod

# Switch context
cloudctl switch azure-prod

# View active context
cloudctl env
```

### Architecture: Azure CLI & Subscriptions

Azure uses the **Azure CLI (`az`)** for authentication against Azure AD.

**Flow:**

```
1. cloudctl login <org>
   ↓
2. Runs: az login [--tenant <id>]
   ↓
3. Browser opens → Azure AD authentication
   ↓
4. Token cached in ~/.azure/
   ↓
5. cloudctl switch <org>
   ↓
6. Lists subscriptions (live query)
   ↓
7. Lists RBAC roles for selected subscription (optional)
   ↓
8. Retrieves access token
   ↓
9. Exports: AZURE_SUBSCRIPTION_ID, ARM_ACCESS_TOKEN, etc.
```

### Concepts: Subscriptions & Tenants

**Tenant:** Azure AD directory (organization)
- Contains users, apps, and RBAC role definitions
- Identified by Tenant ID (UUID)
- One per Azure AD organization

**Subscription:** Billing container under a tenant
- Contains resources (VMs, storage, databases, etc.)
- Identified by Subscription ID (UUID)
- One tenant can have multiple subscriptions

**RBAC Role:** Permission set assigned to a subscription
- Examples: Contributor, Reader, Owner, VM Contributor
- Evaluated per subscription

### Configuration

```yaml
- name: azure-prod
  provider: azure
  tenant_id: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx  # optional but recommended
  allowed_regions: [eastus, westeurope]             # optional
  default_region: eastus
  # roles: optional; if omitted, auto-discovered from subscription RBAC
```

**If tenant_id is omitted:**
- `az login` will prompt for tenant selection
- Good for multi-tenant scenarios

**If tenant_id is provided:**
- `az login --tenant <id>` skips the tenant selection prompt
- Faster, deterministic

### Subscription Auto-Discovery

When you switch to Azure:

```bash
cloudctl switch azure-prod

# Picker shows:
# Subscription? (selecting from live list)
#   ☐ Production (12345678-1234-...)
#   ☐ Development (87654321-4321-...)
#   ☐ Staging (11111111-2222-...)
```

Each subscription is queried live, so the list is always current.

### RBAC Roles

CloudCTL supports two RBAC role discovery modes:

**Auto-Discovery (Default):**

```yaml
- name: azure-prod
  provider: azure
  tenant_id: ...
  # roles: omitted
```

When `roles` is omitted, cloudctl queries Azure RBAC for the selected subscription:

```bash
cloudctl switch azure-prod
# (select subscription)
# Querying RBAC roles for this subscription...
# Role? 
#   ☐ Contributor
#   ☐ Reader
#   ☐ User Access Administrator
```

**Pros:** Accurate, reflects actual permissions  
**Cons:** Slower (requires live Azure API call)

**Static List:**

```yaml
- name: azure-prod
  provider: azure
  tenant_id: ...
  roles:
    - Contributor
    - Reader
    - Owner
```

When `roles` is configured, cloudctl skips the live query:

```bash
cloudctl switch azure-prod
# (select subscription)
# Role? (showing static list)
#   ☐ Contributor
#   ☐ Reader
#   ☐ Owner
```

**Pros:** Fast, predictable  
**Cons:** May not reflect actual permissions if RBAC changes

### Region Support

Azure region names differ from AWS:

| AWS Format | Azure Format |
|---|---|
| us-east-1 | eastus |
| us-west-2 | westus2 |
| eu-west-1 | westeurope |
| ap-southeast-1 | southeastasia |

Configure allowed regions:

```yaml
- name: azure-prod
  provider: azure
  allowed_regions: [eastus, westeurope, southeastasia]
```

Or use `*` for all regions (not recommended).

### Credential Expiry & Refresh

**Token TTL:** 1 hour (Azure default)

**Monitor expiry:**

```bash
cloudctl env
# Expires: 2024-03-15 11:30:00 (in 59 minutes)
```

**Refresh:**

```bash
# Automatic
cloudctl watch --threshold 600  # 10 minutes before expiry

# Manual
cloudctl login azure-prod --force
```

### Environment Variables

When you switch to an Azure context:

```bash
export AZURE_SUBSCRIPTION_ID=<subscription-uuid>
export AZURE_TENANT_ID=<tenant-uuid>
export ARM_SUBSCRIPTION_ID=<subscription-uuid>
export ARM_TENANT_ID=<tenant-uuid>
export ARM_ACCESS_TOKEN=<access-token>
```

**For Terraform:**

```hcl
provider "azurerm" {
  subscription_id = var.subscription_id
  tenant_id       = var.tenant_id
  # Uses ARM_ACCESS_TOKEN from environment
}
```

---

## GCP (Google Cloud Platform)

### Quick Start

```bash
# Add GCP organization
cloudctl org add

# Authenticate (opens browser for Google login)
cloudctl login gcp-prod

# Switch context
cloudctl switch gcp-prod

# View active context
cloudctl env
```

### Architecture: Google Cloud SDK (gcloud)

GCP uses the **Google Cloud SDK (`gcloud`)** for authentication.

**Flow:**

```
1. cloudctl login <org>
   ↓
2. Runs: gcloud auth login
   ↓
3. Browser opens → Google account authentication
   ↓
4. Also runs: gcloud auth application-default login
   ↓
5. Tokens cached in ~/.config/gcloud/
   ↓
6. cloudctl switch <org>
   ↓
7. Lists projects accessible to the user
   ↓
8. Lists IAM roles (configured in org config)
   ↓
9. Retrieves access token
   ↓
10. Exports: GOOGLE_CLOUD_PROJECT, GOOGLE_OAUTH_ACCESS_TOKEN, etc.
```

### Concepts: Projects, Roles, Resources

**Project:** Top-level container for GCP resources
- Identified by project ID (string) or project number (numeric)
- Contains all resources, quotas, billing
- Example: `my-gcp-project-123`

**IAM Role:** Permission set applied to a project
- Predefined roles: `roles/viewer`, `roles/editor`, `roles/owner`
- Custom roles: `roles/custom.myRole`
- Example: a user might have `roles/editor` on project A and `roles/viewer` on project B

**Resource:** Anything inside a project (VM, storage bucket, database, etc.)

**Important:** GCP does not support "role switching" like AWS or Azure. Roles are IAM bindings on the project. When you select a role in cloudctl, it's stored in context for audit purposes but doesn't affect actual permissions (which are determined by IAM).

### Configuration

```yaml
- name: gcp-prod
  provider: gcp
  default_project: my-gcp-project-id             # required
  allowed_regions: [us-central1, europe-west1]   # optional
  default_region: us-central1
  roles:                                          # optional
    - roles/viewer
    - roles/editor
```

**default_project:** Used as `GOOGLE_CLOUD_PROJECT` when you switch. This is the "active" project context.

**roles:** Predefined IAM role names shown in the picker. If omitted, defaults to:
- roles/viewer
- roles/editor
- roles/owner

### Project Auto-Discovery

When you switch to GCP:

```bash
cloudctl switch gcp-prod

# Picker shows:
# Project? (selecting from accessible projects)
#   ☐ production-123 (my-gcp-project-1)
#   ☐ staging-456 (my-gcp-project-2)
#   ☐ dev-789 (my-gcp-project-3)
```

Projects are queried live via `gcloud projects list`.

### Application Default Credentials (ADC)

When you run `cloudctl login gcp-org`, cloudctl runs **both**:

```bash
gcloud auth login                        # User identity
gcloud auth application-default login    # ADC for SDKs/Terraform
```

**ADC** allows Terraform and other SDKs to authenticate without additional setup:

```bash
# After cloudctl login, this works:
terraform plan  # Uses ADC from ~/.config/gcloud/

# Or in code:
gcloud compute instances list
```

### Region Names

GCP uses a different region naming scheme:

| AWS Format | Azure Format | GCP Format |
|---|---|---|
| us-east-1 | eastus | us-east1 |
| us-west-2 | westus2 | us-west2 |
| eu-west-1 | westeurope | europe-west1 |
| ap-southeast-1 | southeastasia | asia-southeast1 |

**Note:** GCP uses hyphens and `1`, `2`, etc., while AWS uses dashes and `-1a`, `-1b`, etc.

Configure allowed regions:

```yaml
- name: gcp-prod
  provider: gcp
  allowed_regions: [us-central1, us-east1, europe-west1]
```

### Credential Expiry & Refresh

**Token TTL:** Exactly 1 hour

**gcloud auto-refresh:**

When you run `gcloud` commands, it automatically refreshes tokens before expiry.

**Monitor expiry:**

```bash
cloudctl env
# Expires: 2024-03-15 11:30:00 (in 59 minutes)
```

**Manual refresh:**

```bash
gcloud auth login      # Re-authenticate user identity
gcloud auth application-default login  # Re-authenticate ADC
```

Or via cloudctl:

```bash
cloudctl login gcp-prod --force
```

### Environment Variables

When you switch to a GCP context:

```bash
export GOOGLE_CLOUD_PROJECT=my-gcp-project-id
export CLOUDSDK_CORE_PROJECT=my-gcp-project-id
export GCLOUD_PROJECT=my-gcp-project-id
export GOOGLE_OAUTH_ACCESS_TOKEN=<access-token>
export GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/application_default_credentials.json
```

**For Terraform:**

```hcl
provider "google" {
  project = var.project_id
  # Uses GOOGLE_APPLICATION_CREDENTIALS from environment
}
```

---

## Feature Comparison Matrix

| Feature | AWS | Azure | GCP |
|---|---|---|---|
| **Authentication** | IAM Identity Center | Azure CLI | gcloud |
| **Token Location** | ~/.aws/sso/cache/ | ~/.azure/ | ~/.config/gcloud/ |
| **Token TTL** | 12 hours | 1 hour | 1 hour |
| **Account Enumeration** | Live (< 2 sec) | Live (< 2 sec) | Live (< 2 sec) |
| **Role Enumeration** | Live (< 2 sec) | Live or Static | Static |
| **Region Filtering** | Partition-aware | Arbitrary | Arbitrary |
| **Partition Support** | aws, aws-us-gov, aws-cn | N/A | N/A |
| **Terraform Support** | ✅ via AWS_* vars | ✅ via ARM_* vars | ✅ via ADC |
| **Multi-Tenant** | N/A | ✅ via tenant_id | N/A |
| **Break-Glass Logging** | ✅ | ✅ | ✅ |
| **Region Naming** | us-east-1, etc. | eastus, etc. | us-east1, etc. |

---

## Multi-Cloud Context Switching

CloudCTL handles switching between clouds seamlessly:

```bash
# Switch to AWS
cloudctl switch bt-avm
cloudctl env
# Org: bt-avm (AWS)
# Account: 111111111111
# Role: AdminAccess
# Region: us-east-1
# Expires: ...

# Switch to Azure
cloudctl switch azure-prod
cloudctl env
# Org: azure-prod (Azure)
# Subscription: 22222222-2222-...
# Role: Contributor
# Region: eastus
# Expires: ...

# Switch to GCP
cloudctl switch gcp-prod
cloudctl env
# Org: gcp-prod (GCP)
# Project: my-gcp-project-id
# Role: roles/viewer
# Region: us-central1
# Expires: ...
```

Each context maintains separate credentials and environment variables.

---

## Troubleshooting: Cloud-Specific Issues

### AWS

**"InvalidClientTokenId" or "NotAuthorizedException"**
- Token has expired or SSO session invalidated
- Solution: `cloudctl login <org> --force`

**"Region is not available"**
- Trying to use a region in the wrong partition (e.g., us-east-1 in GovCloud)
- Solution: Check partition and use correct region for partition

**"AWS CLI v2 not found"**
- AWS CLI not installed or not on PATH
- Solution: `brew install awscli` or `aws --version`

### Azure

**"AADSTS700016: Application with identifier '<id>' not found in the directory"**
- Tenant mismatch or account not in specified tenant
- Solution: Verify tenant_id is correct, or omit it and let az prompt

**"Insufficient privileges to complete the operation"**
- User doesn't have permission for this subscription
- Solution: Check RBAC role assignments in Azure Portal

**"Azure CLI not found"**
- Azure CLI not installed or not on PATH
- Solution: `brew install azure-cli` or https://aka.ms/azure-cli

### GCP

**"ERROR: (gcloud.projects.list) User [xxx] does not have permission"**
- User doesn't have permission to list projects
- Solution: Add user to organization with minimal role (Browser or Viewer)

**"GOOGLE_APPLICATION_CREDENTIALS pointing to file that does not exist"**
- ADC credentials corrupted or deleted
- Solution: `gcloud auth application-default login`

**"gcloud not found"**
- Google Cloud SDK not installed or not on PATH
- Solution: https://cloud.google.com/sdk/docs/install

---

## Best Practices

### Security

1. **Use shortest reasonable token TTLs** — Default 12 hours for AWS, 1 hour for Azure/GCP
2. **Enable break-glass logging** — Configure `sensitive_roles` for audit trail
3. **Restrict allowed regions** — Use `allowed_regions` to prevent misconfigurations
4. **Use partition-specific contexts** — Separate AWS commercial and GovCloud orgs
5. **Refresh before expiry** — Use `cloudctl watch` to keep credentials fresh

### Operations

1. **Use context aliases** for frequently-used contexts:
   ```yaml
   aliases:
     prod:
       org: bt-avm
       account: "111111111111"
       role: AdminAccess
       region: us-east-1
   ```

2. **Monitor credential expiry** during long operations:
   ```bash
   cloudctl watch &
   terraform apply
   ```

3. **Test region constraints** before running infrastructure:
   ```bash
   cloudctl switch <org>
   # Verify region is correct for partition
   ```

4. **Use `cloudctl exec`** for one-off commands without switching context:
   ```bash
   cloudctl exec --org gcp-prod -- gcloud compute instances list
   ```

---

## References

- [docs/DEPLOYMENT.md](./DEPLOYMENT.md) — Installation and setup
- [docs/ARCHITECTURE.md](./ARCHITECTURE.md) — Technical design
- [README.md](../README.md) — User documentation
- `.claude/CLAUDE.md` — Developer guide
