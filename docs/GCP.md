# CloudCtl GCP Operations

> Seamless GCP authentication and organization IAM management

## Quick Start

### 1️⃣ Authenticate with GCP

```bash
cloudctl gcp login --account admin@craighoad.com
```

This will:
- ✅ Open your browser automatically (no copy/paste needed)
- ✅ Handle OAuth2 sign-in
- ✅ Cache credentials for future operations
- ✅ Handle MFA approval on your phone

### 2️⃣ Grant Organization IAM Roles

```bash
cloudctl gcp grant-iam-roles \
  1045595480395 \
  admin@craighoad.com \
  projectCreator \
  folderCreator \
  billing.projectManager \
  folderIamAdmin
```

### 3️⃣ All-In-One Setup (Recommended)

```bash
./scripts/gcp-init.sh 1045595480395 admin@craighoad.com projectCreator folderCreator billing.projectManager folderIamAdmin
```

This single command:
1. Authenticates with GCP
2. Waits for approval
3. Automatically grants all organization roles

## Commands Reference

### `cloudctl gcp login`

Authenticate with GCP using gcloud OAuth2 flow.

```bash
# With explicit email
cloudctl gcp login --account admin@craighoad.com

# Auto-detect from gcloud config
cloudctl gcp login
```

**What it does:**
- Checks if gcloud is installed
- Opens browser automatically for OAuth2
- Handles account mismatch errors with clear guidance
- Confirms success and shows active account
- Caches credentials for other operations

**Troubleshooting:**
- **"Account mismatch"**: Sign out from wrong account in browser, then re-run
- **"gcloud not found"**: Install Google Cloud SDK: `brew install --cask google-cloud-sdk`

### `cloudctl gcp grant-iam-roles`

Grant organization-level IAM roles to a principal.

```bash
cloudctl gcp grant-iam-roles <org-id> <member> <role1> [role2] [role3] ...
```

**Arguments:**
- `<org-id>` — GCP Organization ID (e.g., `1045595480395`)
- `<member>` — Email address (e.g., `admin@craighoad.com`)
- `<role1> [role2] ...` — Role names, auto-prefixed with `roles/` if needed

**Supported roles:**
```
projectCreator            → roles/resourcemanager.projectCreator
folderCreator             → roles/resourcemanager.folderCreator
folderIamAdmin            → roles/resourcemanager.folderIamAdmin
billing.projectManager    → roles/billing.projectManager
... (any GCP role name)
```

**Example:**
```bash
cloudctl gcp grant-iam-roles 1045595480395 admin@craighoad.com \
  projectCreator \
  folderCreator \
  billing.projectManager \
  folderIamAdmin
```

**What it does:**
1. Verifies authentication
2. Refreshes token for org-level operations
3. Grants each role with status output
4. Verifies all roles were granted
5. Shows final IAM binding state

## Complete Workflow Examples

### Phase 0 Setup (Recommended)

```bash
# One command sets up everything:
./scripts/gcp-init.sh 1045595480395 admin@craighoad.com projectCreator folderCreator billing.projectManager folderIamAdmin

# Output:
# ✅ Authenticated
# ✅ Roles granted
# ✅ Ready for Terraform
```

### Manual Step-by-Step

```bash
# Step 1: Login
cloudctl gcp login --account admin@craighoad.com

# (Browser opens, you approve MFA on phone)

# Step 2: Verify
gcloud auth list

# Step 3: Grant roles
cloudctl gcp grant-iam-roles 1045595480395 admin@craighoad.com \
  projectCreator folderCreator billing.projectManager folderIamAdmin

# Step 4: Verify roles
gcloud organizations get-iam-policy 1045595480395 \
  --format=json | \
  jq '.bindings[] | select(.members[] | contains("admin@craighoad.com")) | .role'
```

## Design Notes

### Why the Browser Opens Automatically

`gcloud auth login` natively opens the browser without any scripting:
- macOS: Uses `open` command
- Linux: Tries `xdg-open` or other alternatives
- Windows: Uses `start` command

No Claude automation needed—native OS integration handles it.

### Token Caching

Once authenticated, gcloud caches credentials and tokens:
- Location: `~/.config/gcloud/` (macOS/Linux) or `%APPDATA%\gcloud\` (Windows)
- Duration: ~1 hour (auto-refreshed by gcloud)
- Used by: Terraform, gcloud CLI, SDKs

### MFA & Non-Interactive Mode

- **Interactive**: Browser handles MFA naturally ✅
- **Non-interactive** (CI/CD): Use service accounts instead
- **Cached credentials**: Work in non-interactive contexts after initial login

## Troubleshooting

### "gcloud not found"

Install Google Cloud SDK:
```bash
# macOS
brew install --cask google-cloud-sdk

# Linux
curl https://sdk.cloud.google.com | bash

# Or: https://cloud.google.com/sdk/docs/install
```

### "Account mismatch" Error

The browser was logged into a different Google account.

**Solutions:**
1. **Sign out and back in** (easiest):
   ```bash
   # Sign out from wrong account in your browser
   # Sign in with correct account
   cloudctl gcp login --account admin@craighoad.com
   ```

2. **Use Incognito window** (faster):
   - Open new Incognito/Private window
   - Sign in with correct account
   - Re-run command

### "Reauthentication failed"

Credentials expired or need refresh.

**Solution:**
```bash
cloudctl gcp login --account admin@craighoad.com
```

### "Policy modification failed"

Rare error during role grant—usually succeeds on retry.

**Solution:**
```bash
# Verify roles were actually granted:
gcloud organizations get-iam-policy 1045595480395 \
  --format=json | \
  jq '.bindings[] | select(.members[] | contains("admin@craighoad.com"))'

# If missing, re-run grant:
cloudctl gcp grant-iam-roles 1045595480395 admin@craighoad.com folderCreator
```

## Integration with Terraform

After authenticating, Terraform can use these roles:

```hcl
provider "google" {
  project = var.gcp_project
  # Uses GOOGLE_OAUTH_ACCESS_TOKEN or cached gcloud credentials
}
```

Environment variables set by gcloud (used by Terraform):
- `GOOGLE_CLOUD_PROJECT`
- `CLOUDSDK_CORE_PROJECT`
- `GCLOUD_PROJECT`
- `GOOGLE_OAUTH_ACCESS_TOKEN`

## See Also

- [CloudCtl Documentation](../README.md)
- [GCP Provider (gcp.py)](../src/cloudctl/providers/gcp.py)
- [GCP IAM Command (gcp_iam.py)](../src/cloudctl/commands/gcp_iam.py)
- [GCP Login Command (gcp_login.py)](../src/cloudctl/commands/gcp_login.py)
