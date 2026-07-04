# CloudCtl Configuration Guide — Step-by-Step Setup

**Version:** 1.0 (2026-05-27)  
**Status:** DEFINITIVE — Zero Ambiguity on Configuration  
**Audience:** Claude Code sessions setting up new organizations in CloudCtl  
**Purpose:** Answer every question about configuring orgs.yaml

---

## 🎯 What This Guide Covers

This guide shows you exactly how to:
1. **Set up AWS SSO** in CloudCtl (with real sso_start_url)
2. **Set up Azure Entra** in CloudCtl (with subscription IDs)
3. **Set up GCP OIDC** in CloudCtl (with project IDs)
4. **Add any new organization** to orgs.yaml
5. **Validate your configuration** (what works, what doesn't)
6. **Fix configuration errors** (decision tree troubleshooting)

Every instruction is copy-paste-ready. No ambiguity.

---

## 📍 WHERE IS orgs.yaml?

```
~/.config/cloudctl/orgs.yaml
```

**That's the ONLY place CloudCtl looks.** If it's not there, run:

```bash
cloudctl init
```

This creates a skeleton `~/.config/cloudctl/orgs.yaml` with placeholder organizations. You'll edit this file to add your actual orgs.

---

## 🔍 SKELETON orgs.yaml (What `cloudctl init` Creates)

```yaml
version: "5.1.0"

encrypted_fields:
  - sso_start_url
  - approval_webhook_secret

organizations: {}
```

**What this means:**
- `version: "5.1.0"` — Schema version (do NOT change)
- `encrypted_fields` — These fields are encrypted at rest in the file (do NOT remove)
- `organizations: {}` — Empty dict. You'll add your orgs here.

**Start here.** Then follow the provider-specific sections below to add your organizations.

---

## 🏢 PROVIDER SETUP: AWS SSO

### Step 1: Find Your AWS SSO Start URL

**Location:** AWS IAM Identity Center (formerly AWS SSO) → Settings

**Steps:**
1. Go to AWS Management Console
2. Open **IAM Identity Center** (search for it)
3. Click **Settings** (left sidebar)
4. Under **User portal** section, you'll see:
   - **User portal URL:** `https://YOUR-ACCOUNT-ID.awsapps.com/start`

**Example:**
- If URL is `https://d-1234567890.awsapps.com/start` → sso_start_url = `https://d-1234567890.awsapps.com/start`
- If URL is `https://beyondtrust.awsapps.com/start` → sso_start_url = `https://beyondtrust.awsapps.com/start`

### Step 2: Find Your AWS Account Numbers

**Location:** AWS IAM Identity Center → Organization → Accounts

**Steps:**
1. In IAM Identity Center, click **Organization** (left sidebar)
2. Click **Accounts**
3. You'll see a list of accounts with their **Account IDs** (12-digit numbers)

**Example accounts:**
- Commercial: `235494790978` (bt-avm)
- Dev: `987654321098` (bt-dev)
- GovCloud: `111111111111` (fdr-gvc)
- China: `222222222222` (fdr-cmc-cn)

### Step 3: Find Your Roles in Each Account

**Location:** AWS IAM Identity Center → Accounts → [Account] → Roles

**Steps:**
1. In IAM Identity Center, click **Accounts**
2. Click on an account name
3. Click **Roles** tab
4. You'll see role names like `admin`, `devops`, `security`, `developer`, `readonly`

**Example roles:**
- `admin` (most privileged)
- `devops` (deployment, automation)
- `security` (security operations)
- `developer` (read + dev access)
- `readonly` (read-only access)

### Step 4: Create AWS Entry in orgs.yaml

**Template:**

```yaml
organizations:
  bt-avm:
    provider: aws
    partition: aws
    sso_start_url: "https://d-1234567890.awsapps.com/start"
    sensitive_roles: ["admin", "security"]
    approval_gate_roles:
      admin: 2
      security: 1
    mfa_required_roles: ["admin", "security"]
    approval_provider: "mock"
    approval_timeout_seconds: 300
```

**Field Explanation:**

| Field | Value | Meaning |
|-------|-------|---------|
| `bt-avm` | Organization name (you choose) | Reference name for CloudCtl commands |
| `provider` | `aws` | This is AWS (not azure or gcp) |
| `partition` | `aws` | Standard AWS partition (OR `aws-us-gov` for GovCloud, `aws-cn` for China) |
| `sso_start_url` | Your AWS SSO URL | From Step 1 above |
| `sensitive_roles` | `["admin", "security"]` | Roles that require approval/MFA |
| `approval_gate_roles` | Dict of role → approver count | How many approvers each sensitive role needs (1 or 2) |
| `mfa_required_roles` | `["admin", "security"]` | Roles that require MFA (subset of sensitive_roles) |
| `approval_provider` | `mock` | Use mock for Phase 1 (auto-approves for testing) |
| `approval_timeout_seconds` | `300` | Wait up to 5 minutes for approval |

### Step 5: Validate AWS Configuration

```bash
cloudctl doctor
```

**Expected output:**
```
✅ Health: healthy
   - orgs.yaml valid
   - aws provider configured
   - sso_start_url reachable
   - encryption keys present
```

**If unhealthy:** See **Troubleshooting** section below.

### Real Example: BeyondTrust AWS Setup

```yaml
organizations:
  bt-avm:
    provider: aws
    partition: aws
    sso_start_url: "https://beyondtrust.awsapps.com/start"
    sensitive_roles: ["admin", "devops", "security"]
    approval_gate_roles:
      admin: 2
      devops: 1
      security: 2
    mfa_required_roles: ["admin", "security"]
    approval_provider: "mock"
    approval_timeout_seconds: 300

  bt-dev:
    provider: aws
    partition: aws
    sso_start_url: "https://beyondtrust.awsapps.com/start"
    sensitive_roles: ["admin"]
    approval_gate_roles:
      admin: 1
    mfa_required_roles: ["admin"]
    approval_provider: "mock"
    approval_timeout_seconds: 300

  fdr-gvc:
    provider: aws
    partition: aws
    sso_start_url: "https://beyondtrust.awsapps.com/start"
    sensitive_roles: ["admin", "security"]
    approval_gate_roles:
      admin: 2
      security: 1
    mfa_required_roles: ["admin", "security"]
    approval_provider: "mock"
    approval_timeout_seconds: 300
```

---

## 🏢 PROVIDER SETUP: Azure Entra

### Step 1: Find Your Azure Entra Directory ID

**Location:** Azure Portal → Azure Active Directory → Properties

**Steps:**
1. Go to **Azure Portal** (portal.azure.com)
2. Search for **Azure Active Directory** (or **Entra ID**)
3. Click **Properties**
4. Copy the **Directory ID** (UUID format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

**Example:**
- Directory ID: `12345678-1234-1234-1234-123456789012`

### Step 2: Find Your Subscriptions

**Location:** Azure Portal → Subscriptions

**Steps:**
1. In Azure Portal, search for **Subscriptions**
2. You'll see a list of subscriptions with their **Subscription IDs** (UUID format)

**Example subscriptions:**
- Production: `/subscriptions/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa`
- Development: `/subscriptions/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb`
- DevTest: `/subscriptions/cccccccc-cccc-cccc-cccc-cccccccccccc`

### Step 3: Find Your Roles in Each Subscription

**Location:** Azure Portal → Subscriptions → [Subscription] → Access Control (IAM) → Role Assignments

**Steps:**
1. Go to each subscription
2. Click **Access Control (IAM)** (left sidebar)
3. Click **Role Assignments** tab
4. Find Azure built-in roles:
   - `Owner` (full admin)
   - `Contributor` (can create/modify resources)
   - `Reader` (read-only)
   - Or custom roles specific to your org

**Example roles:**
- `Owner` (most privileged)
- `Contributor` (deployment, automation)
- `Reader` (read-only access)

### Step 4: Create Azure Entry in orgs.yaml

**Template:**

```yaml
organizations:
  avm-prod:
    provider: azure
    sso_start_url: "https://login.microsoftonline.com/12345678-1234-1234-1234-123456789012"
    sensitive_roles: ["Owner", "Contributor"]
    approval_gate_roles:
      Owner: 2
      Contributor: 1
    mfa_required_roles: ["Owner"]
    approval_provider: "mock"
    approval_timeout_seconds: 300
```

**Field Explanation:**

| Field | Value | Meaning |
|-------|-------|---------|
| `avm-prod` | Organization name (you choose) | Reference name for CloudCtl commands |
| `provider` | `azure` | This is Azure (not aws or gcp) |
| `sso_start_url` | Microsoft login + directory ID | `https://login.microsoftonline.com/[Directory ID]` |
| `sensitive_roles` | `["Owner"]` | Roles that require approval/MFA |
| `approval_gate_roles` | Dict of role → approver count | How many approvers each role needs (1 or 2) |
| `mfa_required_roles` | `["Owner"]` | Roles that require MFA |
| `approval_provider` | `mock` | Use mock for Phase 1 |
| `approval_timeout_seconds` | `300` | Wait up to 5 minutes for approval |

### Step 5: Validate Azure Configuration

```bash
cloudctl doctor
```

**Expected output:**
```
✅ Health: healthy
   - orgs.yaml valid
   - azure provider configured
   - sso_start_url reachable
   - encryption keys present
```

### Real Example: BeyondTrust Azure Setup

```yaml
organizations:
  avm-prod:
    provider: azure
    sso_start_url: "https://login.microsoftonline.com/12345678-1234-1234-1234-123456789012"
    sensitive_roles: ["Owner", "Contributor"]
    approval_gate_roles:
      Owner: 2
      Contributor: 1
    mfa_required_roles: ["Owner"]
    approval_provider: "mock"
    approval_timeout_seconds: 300

  avm-dev:
    provider: azure
    sso_start_url: "https://login.microsoftonline.com/12345678-1234-1234-1234-123456789012"
    sensitive_roles: ["Owner"]
    approval_gate_roles:
      Owner: 1
    mfa_required_roles: ["Owner"]
    approval_provider: "mock"
    approval_timeout_seconds: 300
```

---

## 🏢 PROVIDER SETUP: GCP OIDC

### Step 1: Find Your GCP Project IDs

**Location:** Google Cloud Console → Project Info

**Steps:**
1. Go to **Google Cloud Console** (console.cloud.google.com)
2. At the top, you'll see a project dropdown
3. Click it to see all projects
4. Each project shows its **Project ID** (e.g., `my-project-123456`)

**Example projects:**
- Production: `prod-cloud-123456`
- Development: `dev-cloud-789012`
- Staging: `staging-cloud-345678`

### Step 2: Find Your Roles in Each Project

**Location:** Google Cloud Console → Projects → [Project] → IAM & Admin → Roles

**Steps:**
1. Go to each project
2. Click **IAM & Admin** (left sidebar)
3. Click **Roles**
4. You'll see predefined Google Cloud roles:
   - `Owner` (full admin, can delete project)
   - `Editor` (create/modify resources)
   - `Viewer` (read-only)
   - Or custom roles

**Example roles:**
- `roles/owner` (most privileged)
- `roles/editor` (deployment, automation)
- `roles/viewer` (read-only access)

### Step 3: Create GCP Entry in orgs.yaml

**Template:**

```yaml
organizations:
  gcp-prod:
    provider: gcp
    sensitive_roles: ["Owner", "Editor"]
    approval_gate_roles:
      Owner: 2
      Editor: 1
    mfa_required_roles: ["Owner"]
    approval_provider: "mock"
    approval_timeout_seconds: 300
```

**Field Explanation:**

| Field | Value | Meaning |
|-------|-------|---------|
| `gcp-prod` | Organization name (you choose) | Reference name for CloudCtl commands |
| `provider` | `gcp` | This is GCP (not aws or azure) |
| `sensitive_roles` | `["Owner", "Editor"]` | Roles that require approval/MFA |
| `approval_gate_roles` | Dict of role → approver count | How many approvers each role needs (1 or 2) |
| `mfa_required_roles` | `["Owner"]` | Roles that require MFA |
| `approval_provider` | `mock` | Use mock for Phase 1 |
| `approval_timeout_seconds` | `300` | Wait up to 5 minutes for approval |

**Note:** GCP does NOT require `sso_start_url` (uses OIDC federation directly)

### Step 4: Validate GCP Configuration

```bash
cloudctl doctor
```

**Expected output:**
```
✅ Health: healthy
   - orgs.yaml valid
   - gcp provider configured
   - OIDC federation active
   - encryption keys present
```

### Real Example: BeyondTrust GCP Setup

```yaml
organizations:
  gcp-prod:
    provider: gcp
    sensitive_roles: ["Owner", "Editor"]
    approval_gate_roles:
      Owner: 2
      Editor: 1
    mfa_required_roles: ["Owner"]
    approval_provider: "mock"
    approval_timeout_seconds: 300

  gcp-dev:
    provider: gcp
    sensitive_roles: ["Owner"]
    approval_gate_roles:
      Owner: 1
    mfa_required_roles: ["Owner"]
    approval_provider: "mock"
    approval_timeout_seconds: 300
```

---

## 📋 COMPLETE EXAMPLE: Multi-Cloud Setup (AWS + Azure + GCP)

Here's a production-ready orgs.yaml with all three clouds:

```yaml
version: "5.1.0"

encrypted_fields:
  - sso_start_url
  - approval_webhook_secret

organizations:
  # ========== AWS (Commercial) ==========
  bt-avm:
    provider: aws
    partition: aws
    sso_start_url: "https://beyondtrust.awsapps.com/start"
    sensitive_roles: ["admin", "devops", "security"]
    approval_gate_roles:
      admin: 2
      devops: 1
      security: 2
    mfa_required_roles: ["admin", "security"]
    approval_provider: "mock"
    approval_timeout_seconds: 300

  bt-dev:
    provider: aws
    partition: aws
    sso_start_url: "https://beyondtrust.awsapps.com/start"
    sensitive_roles: ["admin"]
    approval_gate_roles:
      admin: 1
    mfa_required_roles: ["admin"]
    approval_provider: "mock"
    approval_timeout_seconds: 300

  # ========== AWS (GovCloud) ==========
  fdr-gvc:
    provider: aws
    partition: aws-us-gov
    sso_start_url: "https://fdr-gvc.awsapps.com/start"
    sensitive_roles: ["admin", "security"]
    approval_gate_roles:
      admin: 2
      security: 1
    mfa_required_roles: ["admin", "security"]
    approval_provider: "mock"
    approval_timeout_seconds: 300

  # ========== AWS (China) ==========
  fdr-cmc-cn:
    provider: aws
    partition: aws-cn
    sso_start_url: "https://fdr-cmc-cn.awsapps.cn/start"
    sensitive_roles: ["admin"]
    approval_gate_roles:
      admin: 2
    mfa_required_roles: ["admin"]
    approval_provider: "mock"
    approval_timeout_seconds: 300

  # ========== Azure ==========
  avm-prod:
    provider: azure
    sso_start_url: "https://login.microsoftonline.com/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    sensitive_roles: ["Owner", "Contributor"]
    approval_gate_roles:
      Owner: 2
      Contributor: 1
    mfa_required_roles: ["Owner"]
    approval_provider: "mock"
    approval_timeout_seconds: 300

  # ========== GCP ==========
  gcp-prod:
    provider: gcp
    sensitive_roles: ["Owner", "Editor"]
    approval_gate_roles:
      Owner: 2
      Editor: 1
    mfa_required_roles: ["Owner"]
    approval_provider: "mock"
    approval_timeout_seconds: 300
```

---

## ✅ VALIDATION CHECKLIST

After you add an organization, run this checklist:

### 1. File Syntax

```bash
python3 -c "import yaml; yaml.safe_load(open(os.path.expanduser('~/.config/cloudctl/orgs.yaml'))); print('✅ YAML syntax valid')"
```

Expected: `✅ YAML syntax valid`

### 2. CloudCtl Doctor

```bash
cloudctl doctor
```

Expected: `exit_code 0, status: "healthy"`

### 3. List Organizations

```bash
cloudctl org list
```

Expected: Your new organization appears in the list

### 4. List Roles

```bash
cloudctl list-roles <org-name>
```

Expected: Roles for that org are listed (admin, devops, etc.)

### 5. Validate Each Field

Check that your orgs.yaml has:
- ✅ `version: "5.1.0"`
- ✅ `encrypted_fields: [sso_start_url, ...]`
- ✅ `organizations:` dict (not empty)
- ✅ At least one org with:
  - ✅ `provider:` (aws, azure, or gcp)
  - ✅ `partition:` (for AWS only: aws, aws-us-gov, or aws-cn)
  - ✅ `sso_start_url:` (for AWS/Azure only, NOT for GCP)
  - ✅ `sensitive_roles:` (list of role names)
  - ✅ `approval_gate_roles:` (dict mapping roles to approver count)
  - ✅ `mfa_required_roles:` (subset of sensitive_roles)
  - ✅ `approval_provider:` ("mock" for Phase 1)
  - ✅ `approval_timeout_seconds:` (300 recommended)

**If all checks pass** → Your configuration is valid and ready to use.

---

## 🔧 TROUBLESHOOTING CONFIGURATION ERRORS

### Problem: `cloudctl doctor` Says "Unhealthy"

**Decision Tree:**

1. **Check file exists:**
   ```bash
   ls -la ~/.config/cloudctl/orgs.yaml
   ```
   - If `No such file or directory` → Run `cloudctl init`
   - If file exists → Go to step 2

2. **Check YAML syntax:**
   ```bash
   python3 -c "import yaml; yaml.safe_load(open(os.path.expanduser('~/.config/cloudctl/orgs.yaml'))); print('✅ Valid')"
   ```
   - If error → Fix YAML syntax (indentation, quotes, colons)
   - If valid → Go to step 3

3. **Check orgs.yaml has required fields:**
   ```bash
   python3 << 'EOF'
   import yaml
   cfg = yaml.safe_load(open(os.path.expanduser('~/.config/cloudctl/orgs.yaml')))
   assert 'version' in cfg, "Missing: version"
   assert 'organizations' in cfg, "Missing: organizations"
   assert len(cfg['organizations']) > 0, "organizations dict is empty"
   for name, org in cfg['organizations'].items():
       assert 'provider' in org, f"{name}: missing provider"
       assert org['provider'] in ['aws', 'azure', 'gcp'], f"{name}: invalid provider"
   print("✅ All required fields present")
   EOF
   ```
   - If error → Add missing fields
   - If valid → Go to step 4

4. **Check encryption key:**
   ```bash
   ls -la ~/.config/cloudctl/.encryption_key
   ```
   - If `No such file or directory` → Run `cloudctl init` again
   - If exists → Go to step 5

5. **Check AWS SSO URL is reachable (AWS only):**
   ```bash
   python3 << 'EOF'
   import yaml
   import requests
   cfg = yaml.safe_load(open(os.path.expanduser('~/.config/cloudctl/orgs.yaml')))
   for name, org in cfg['organizations'].items():
       if org['provider'] == 'aws':
           url = org.get('sso_start_url')
           try:
               r = requests.head(url, timeout=5, allow_redirects=True)
               print(f"✅ {name}: SSO URL reachable ({r.status_code})")
           except Exception as e:
               print(f"❌ {name}: SSO URL unreachable: {e}")
   EOF
   ```
   - If any unreachable → Check URL spelling, VPN connectivity
   - If all reachable → Go to step 6

6. **If still unhealthy:** Escalate to infra with output from all steps above.

### Problem: `cloudctl list-roles <org>` Returns Empty or Error

**Cause:** Role mapping issue or provider misconfiguration

**Steps:**
1. Verify org name matches exactly: `cloudctl org list`
2. Verify provider in orgs.yaml: `grep "provider:" ~/.config/cloudctl/orgs.yaml`
3. For AWS: Verify sso_start_url is correct (from your AWS SSO settings)
4. For Azure: Verify sso_start_url has correct Directory ID
5. For GCP: Verify provider is `gcp` (no sso_start_url needed)
6. Run `cloudctl doctor` to check overall health
7. If still failing: Escalate to infra with orgs.yaml snippet (remove sso_start_url for security)

### Problem: `cloudctl login <org>` Fails

**Cause:** Authentication or configuration issue

**Steps:**
1. Verify org exists: `cloudctl org list | grep <org>`
2. Verify doctor is healthy: `cloudctl doctor`
3. Verify sso_start_url is correct:
   - AWS: Should be `https://*.awsapps.com/start`
   - Azure: Should be `https://login.microsoftonline.com/*`
   - GCP: Don't need sso_start_url (OIDC federation)
4. Check VPN/network connectivity (especially for gov/internal networks)
5. Try again: `cloudctl login <org>`
6. If still failing: Escalate to infra with error message

### Problem: Role Not Found When Running `cloudctl switch`

**Cause:** Role name doesn't match, or role not assigned to your user

**Steps:**
1. List available roles: `cloudctl list-roles <org>`
2. Copy exact role name (case-sensitive)
3. Try switch: `cloudctl switch <org> <account> <exact-role-name>`
4. If role in list but still not found: Contact your org admin—role may not be assigned to you
5. If role not in list: Add it to orgs.yaml `sensitive_roles` or `approval_gate_roles`

### Problem: `cloudctl doctor` Says "Encryption Key Missing"

**Cause:** `.encryption_key` file deleted or corrupted

**Steps:**
1. Check if file exists: `ls -la ~/.config/cloudctl/.encryption_key`
2. If missing: Run `cloudctl init` (generates new key)
3. If exists but corrupted: Delete and run `cloudctl init` (re-initializes)

**Warning:** If you delete the encryption key, any previously encrypted sensitive_roles in orgs.yaml become unreadable. Only do this if you haven't configured sensitive_roles yet.

---

## ⚠️ COMMON MISTAKES & FIXES

| Mistake | What Happens | Fix |
|---------|--------------|-----|
| **Wrong file location** | `cloudctl doctor` says file not found | Move to `~/.config/cloudctl/orgs.yaml` |
| **YAML indentation** | `doctor` says invalid syntax | Use spaces (not tabs), 2-space indentation |
| **Missing provider** | Organization ignored by CloudCtl | Add `provider: aws/azure/gcp` to each org |
| **Typo in sso_start_url** | Login fails with auth error | Copy exact URL from AWS/Azure console |
| **Role name mismatch** | Role not found in list | Use exact role name from IAM console (case-sensitive) |
| **Empty organizations dict** | No orgs appear in list | Add at least one org under `organizations:` |
| **Quotes in YAML** | Parser fails on special characters | Use double quotes around URLs/role names |
| **GCP has sso_start_url** | Doctor warns about invalid field | Remove `sso_start_url` for GCP (uses OIDC only) |
| **approval_gate_roles empty** | Sensitive roles not enforced | Map each sensitive role to 1 or 2 approvers |
| **No encrypted_fields** | Secrets stored in plaintext | Add `encrypted_fields: [sso_start_url, ...]` |

---

## 🚀 STEP-BY-STEP: Add Your First Organization

### For AWS Users

1. **Get your sso_start_url:**
   - AWS Console → IAM Identity Center → Settings → User portal URL
   - Example: `https://beyondtrust.awsapps.com/start`

2. **Get your account ID:**
   - AWS Console → IAM Identity Center → Accounts
   - Example: `235494790978`

3. **Get your roles:**
   - AWS Console → IAM Identity Center → Accounts → [Your Account] → Roles
   - Example: `admin`, `devops`, `developer`

4. **Edit ~/.config/cloudctl/orgs.yaml:**
   ```yaml
   version: "5.1.0"
   encrypted_fields:
     - sso_start_url
     - approval_webhook_secret
   
   organizations:
     my-org:
       provider: aws
       partition: aws
       sso_start_url: "https://beyondtrust.awsapps.com/start"
       sensitive_roles: ["admin"]
       approval_gate_roles:
         admin: 2
       mfa_required_roles: ["admin"]
       approval_provider: "mock"
       approval_timeout_seconds: 300
   ```

5. **Validate:**
   ```bash
   cloudctl doctor
   cloudctl org list
   cloudctl list-roles my-org
   ```

6. **Test login:**
   ```bash
   cloudctl login my-org
   ```

**Done.** Your first organization is configured.

### For Azure Users

Same steps, but:
- Get **Directory ID** from Azure AD Properties (instead of sso_start_url parts)
- sso_start_url format: `https://login.microsoftonline.com/[Directory ID]`
- Roles are Azure built-in roles: `Owner`, `Contributor`, `Reader`

### For GCP Users

Same steps, but:
- Don't include `sso_start_url` (GCP uses OIDC only)
- GCP handles authentication natively
- Roles are GCP built-in roles: `roles/owner`, `roles/editor`, `roles/viewer`

---

## 📞 WHEN TO ESCALATE

If you've followed this guide and:
- ✅ YAML syntax is valid
- ✅ `cloudctl doctor` is healthy
- ✅ Org list shows your organization
- ✅ But authentication still fails

**Then escalate to infra** with:
- Your orgs.yaml (remove sensitive fields)
- Output of `cloudctl doctor`
- Error message from `cloudctl login`
- Whether you can access the cloud provider console directly (AWS/Azure/GCP)

---

## ✅ YOU'RE READY

Once you complete this guide:
- ✅ You know how to find SSO URLs for each provider
- ✅ You know how to configure orgs.yaml
- ✅ You know how to validate your configuration
- ✅ You know how to troubleshoot errors
- ✅ You've added at least one organization

**Run your first test:**

```bash
cloudctl doctor
cloudctl login my-org
cloudctl env
cloudctl logout
```

If all commands complete successfully → **You're done. CloudCtl is ready to use.**

---

**Last Updated:** 2026-05-27  
**Status:** DEFINITIVE — Zero Ambiguity on Configuration  
**Next:** See CLAUDE_CODE_ORIENTATION.md for how to TEST CloudCtl
