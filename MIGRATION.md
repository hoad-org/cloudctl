# Migration Guide: awsctl → cloudctl v4.0.0

**Release Date:** 2026-04-25  
**Previous Version:** awsctl v3.1.0  
**New Version:** cloudctl v4.0.0  
**Migration Effort:** Low (rename only, no feature changes)

---

## Overview

cloudctl v4.0.0 is a major version release that renames the tool from `awsctl` to `cloudctl`. The rename reflects the tool's multi-cloud capabilities (AWS, Azure, GCP) more accurately than the AWS-specific "awsctl" naming.

**This is a breaking change for shell scripts, configurations, and automation.** However, the functionality is identical—only the command name and package name have changed.

---

## What Changed

### Package & Command Names

| Item | Before | After |
|------|--------|-------|
| **PyPI Package Name** | `awsctl` | `cloudctl` |
| **Main Command** | `awsctl` | `cloudctl` |
| **Binary Alias** | `_awsctl_bin` | `_cloudctl_bin` |
| **Shell Function** | `awsctl()` | `cloudctl()` |
| **Config Directory** | `~/.config/awsctl/` | `~/.config/cloudctl/` |
| **Cache Directory** | `~/.aws/sso/cache/` | `~/.aws/sso/cache/` (unchanged) |

### Version Bump

- **Major version:** 3 → 4 (breaking change due to rename)
- **Minor/Patch:** Reset to .0.0 (semantic versioning)

### No Feature Changes

- ✅ All AWS provider functionality identical
- ✅ All GCP provider functionality identical
- ✅ All Azure provider functionality identical
- ✅ All configuration options unchanged
- ✅ All error handling unchanged
- ✅ Security model unchanged

---

## Migration Path

### Step 1: Uninstall Previous Version

```bash
# If installed via pip
pip uninstall -y awsctl

# If installed via Homebrew
brew uninstall awsctl

# If installed from source
rm -rf ~/.local/bin/awsctl
rm -rf ~/.local/bin/_awsctl_bin
```

### Step 2: Install New Version

**Option A: PyPI (recommended)**

```bash
pip install --upgrade cloudctl
```

**Option B: Homebrew**

```bash
brew tap BT-IT-Infrastructure-CloudOps/cloudctl
brew install cloudctl
```

**Option C: From Source**

```bash
git clone https://github.com/BT-IT-Infrastructure-CloudOps/aws-terraform-infra-cloudops-cloudctl.git
cd aws-terraform-infra-cloudops-cloudctl
pip install -e .
```

### Step 3: Update Shell Configuration

Your shell function wrapper needs to be updated.

**For ~/.bashrc or ~/.bash_profile:**

```bash
# REMOVE the old awsctl function:
# ... (delete all lines of the old awsctl shell function)

# ADD the new cloudctl function:
# Paste the output of: pip show cloudctl | grep Location
# Then add the function from the cloudctl package
```

Or use the installer script:

```bash
source <(pip show cloudctl | grep Location | cut -d: -f2)/cloudctl/shell_setup.sh
```

**For ~/.zshrc:**

Same process as bash:

```bash
# REMOVE old awsctl function from ~/.zshrc
# ADD new cloudctl function
```

### Step 4: Migrate Configuration

The configuration directory needs to be renamed:

```bash
# Backup old configuration
cp -r ~/.config/awsctl ~/.config/awsctl.backup

# Copy to new location
mkdir -p ~/.config/cloudctl
cp -r ~/.config/awsctl/* ~/.config/cloudctl/

# Verify migration
cloudctl list
```

**Note:** The context file (`~/.config/awsctl/context.json`) will automatically be copied to `~/.config/cloudctl/context.json` on first use of cloudctl.

### Step 5: Update Shell Functions & Aliases

If you have custom shell functions or aliases that call `awsctl`, update them:

```bash
# BEFORE
alias switchaws='awsctl switch bt-avm'

# AFTER
alias switchaws='cloudctl switch bt-avm'
```

### Step 6: Update Scripts and Automation

**If you use awsctl in scripts**, update all references:

```bash
#!/bin/bash

# BEFORE
awsctl login myorg
awsctl switch myorg account-id role

# AFTER
cloudctl login myorg
cloudctl switch myorg account-id role
```

### Step 7: Verify Installation

```bash
# Verify command is available
which cloudctl

# Test basic functionality
cloudctl list              # Show configured organizations
cloudctl env               # Show current context
cloudctl login <org>       # Re-authenticate (if needed)
```

---

## Detailed Configuration Migration

### Automatic Migration

When you first run `cloudctl`, it will:

1. Detect existing `~/.config/awsctl/` configuration
2. Automatically copy it to `~/.config/cloudctl/`
3. Preserve all organization settings
4. Preserve all cached credentials

### Manual Migration (if needed)

```bash
# If automatic migration doesn't work:

# 1. Create new config directory
mkdir -p ~/.config/cloudctl

# 2. Copy organization configs
cp -r ~/.config/awsctl/orgs ~/.config/cloudctl/

# 3. Copy current context
cp ~/.config/awsctl/context.json ~/.config/cloudctl/context.json 2>/dev/null || true

# 4. Verify
ls -la ~/.config/cloudctl/
```

### Configuration File Locations

| File | Before | After | Auto-Migrated |
|------|--------|-------|---|
| **Context** | `~/.config/awsctl/context.json` | `~/.config/cloudctl/context.json` | ✅ Yes |
| **Organizations** | `~/.config/awsctl/orgs/` | `~/.config/cloudctl/orgs/` | ✅ Yes |
| **Registry** | `~/.config/awsctl/registry.yaml` | `~/.config/cloudctl/registry.yaml` | ✅ Yes |
| **Cache** | `~/.aws/sso/cache/` | `~/.aws/sso/cache/` | ✅ Unchanged |

---

## Common Migration Scenarios

### Scenario 1: Git CI/CD Pipeline

**Before:**
```yaml
# .github/workflows/deploy.yml
- name: Authenticate with AWS
  run: |
    awsctl login production
    awsctl switch production prod-account prod-role
    terraform plan
```

**After:**
```yaml
# .github/workflows/deploy.yml
- name: Authenticate with AWS
  run: |
    cloudctl login production
    cloudctl switch production prod-account prod-role
    terraform plan
```

### Scenario 2: Docker Image

**Before:**
```dockerfile
FROM python:3.12
RUN pip install awsctl
RUN awsctl init myorg aws ...
```

**After:**
```dockerfile
FROM python:3.12
RUN pip install cloudctl
RUN cloudctl init myorg aws ...
```

### Scenario 3: Terraform Cloud/Enterprise

**Before:**
```hcl
# If you stored credentials using awsctl:
# No change needed — credentials in ~/.aws/config are provider-independent
```

**After:**
```hcl
# Credentials still work the same way
# cloudctl simply manages ~/.aws/config
```

---

## Rollback Instructions

If you need to roll back to awsctl v3.1.0:

```bash
# 1. Uninstall cloudctl
pip uninstall -y cloudctl

# 2. Restore backup configuration
rm -rf ~/.config/cloudctl
mv ~/.config/awsctl.backup ~/.config/awsctl

# 3. Reinstall awsctl
pip install awsctl==3.1.0

# 4. Update shell function
# (restore from git history or reinstall from awsctl)
```

---

## Breaking Changes Summary

### What Will Break

1. ✗ Shell scripts calling `awsctl` command
2. ✗ Aliases or functions that reference `awsctl`
3. ✗ Terraform or Ansible automation using `awsctl`
4. ✗ Docker/container configurations with `awsctl`
5. ✗ CI/CD pipelines referencing `awsctl`

### What Will NOT Break

1. ✅ AWS credentials and tokens (still in `~/.aws/`)
2. ✅ GCP authentication (still in `~/.config/gcloud/`)
3. ✅ Azure authentication (still in `~/.azure/`)
4. ✅ Terraform state files
5. ✅ Existing AWS/GCP/Azure infrastructure
6. ✅ Any command that directly calls AWS, GCP, or Azure CLIs

---

## Testing the Migration

After completing the migration, verify everything works:

```bash
# Test 1: Command exists
cloudctl --version
# Expected: cloudctl 4.0.0

# Test 2: Configuration loaded
cloudctl list
# Expected: List of configured organizations

# Test 3: Context switching
cloudctl switch <org> <account> <role>
# Expected: Context switched successfully

# Test 4: Actual cloud operations
aws sts get-caller-identity
# Expected: Shows your current AWS identity

# Test 5: Multi-cloud
cloudctl switch <gcp-org> <project> <role>
gcloud projects describe $GOOGLE_CLOUD_PROJECT
# Expected: Shows GCP project details
```

---

## FAQ

### Q: Do I need to re-authenticate with cloud providers?

**A:** No. Your credentials in `~/.aws/`, `~/.config/gcloud/`, and `~/.azure/` are unchanged. cloudctl just manages these. If your credentials are expired, use `cloudctl login <org>` to refresh them—this works the same as before.

### Q: Will my existing organizations still work?

**A:** Yes. cloudctl automatically migrates your organization configurations from `~/.config/awsctl/` to `~/.config/cloudctl/` on first run.

### Q: Can I run awsctl and cloudctl side-by-side?

**A:** Not recommended. They will conflict over the shell function name. Migrate completely before running both versions.

### Q: What if I have many scripts using awsctl?

**A:** Use a sed script to bulk-update them:

```bash
find . -type f -name "*.sh" -o -name "*.yaml" -o -name "*.yml" \
  -exec sed -i 's/awsctl/cloudctl/g' {} +
```

### Q: Are there any security changes?

**A:** No. The security model is identical. Shell injection protection, credential handling, and audit logging are unchanged.

### Q: Will Docker images using awsctl need rebuilding?

**A:** Yes. You'll need to rebuild images that install cloudctl instead of awsctl. The Dockerfile change is minimal (one line).

### Q: What about Homebrew formulas?

**A:** The Homebrew formula is available at:
```
brew tap BT-IT-Infrastructure-CloudOps/cloudctl
brew install cloudctl
```

### Q: Is cloudctl backward compatible?

**A:** No. The command name changed, so scripts and automation will need updates. However, the functionality is 100% compatible.

---

## Support & Troubleshooting

### Issue: "cloudctl: command not found"

**Solution:**
```bash
# Verify installation
pip show cloudctl

# Verify in PATH
which cloudctl

# If not in PATH, add to shell config
echo 'export PATH="/path/to/cloudctl:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### Issue: "No valid organizations configured"

**Solution:**
```bash
# Check if configuration was migrated
ls -la ~/.config/cloudctl/

# If empty, restore from backup
cp -r ~/.config/awsctl/* ~/.config/cloudctl/
```

### Issue: "Cannot find AWS credentials"

**Solution:**
```bash
# Verify AWS credentials still exist
ls -la ~/.aws/sso/cache/

# Refresh credentials if needed
cloudctl login <org>
```

### Issue: Shell function not working

**Solution:**
```bash
# Reinstall shell function
source <(pip show cloudctl | grep Location | cut -d: -f2)/cloudctl/shell_setup.sh

# Verify in shell
type cloudctl
```

---

## Timeline

| Date | Event |
|------|-------|
| 2026-04-25 | cloudctl v4.0.0 released |
| 2026-05-25 | awsctl v3.1.0 support ends (30 days) |
| 2026-06-25 | awsctl removed from PyPI (60 days) |

---

## Related Documentation

- [README.md](./README.md) — cloudctl documentation
- [CLAUDE.md](./CLAUDE.md) — Development environment setup
- [CHANGELOG.md](./CHANGELOG.md) — Version history

---

**Questions or issues?** Open an issue at: [github.com/BT-IT-Infrastructure-CloudOps/aws-terraform-infra-cloudops-cloudctl/issues](https://github.com/BT-IT-Infrastructure-CloudOps/aws-terraform-infra-cloudops-cloudctl/issues)

---

**Migration Guide Version:** 1.0  
**Last Updated:** 2026-04-25
