# cloudctl v4.0.0 Migration Guide

## Overview

**awsctl has been renamed to cloudctl** to better reflect its multi-cloud capabilities. cloudctl now supports AWS, Azure, and Google Cloud Platform equally.

This is a **major version bump** (v3.1.0 → v4.0.0) due to breaking CLI changes.

---

## What's Changed

### Command Name
- **Before**: `awsctl` command
- **After**: `cloudctl` command

### Configuration Paths
- **Before**: `~/.awsctl/` and `~/.config/awsctl/`
- **After**: `~/.cloudctl/` and `~/.config/cloudctl/`

### Package Name
- **Before**: `awsctl` (Python package)
- **After**: `cloudctl` (Python package)

### Version
- **Before**: v3.1.0
- **After**: v4.0.0

---

## Upgrade Instructions

### Step 1: Uninstall Old Version
```bash
# Remove old shell integration
awsctl uninstall

# Or manually remove from shell profile
# Edit ~/.bashrc, ~/.zshrc, or ~/.profile
# Remove the awsctl initialization block
```

### Step 2: Install cloudctl
```bash
# Install new version
pip install --upgrade cloudctl

# Or via poetry
poetry add cloudctl
```

### Step 3: Initialize cloudctl
```bash
# Initialize for your shell (bash/zsh/fish/PowerShell)
cloudctl init
```

### Step 4: Migrate Configuration (Optional)
If you have existing organizations configured, cloudctl will automatically detect them:

```bash
cloudctl doctor
```

If the `doctor` command shows that your old `~/.awsctl/` configuration was detected, you can manually copy it:

```bash
# If you had ~/.awsctl/context.json
cp ~/.awsctl/context.json ~/.cloudctl/context.json

# If you had ~/.config/awsctl/orgs.yaml
cp ~/.config/awsctl/orgs.yaml ~/.config/cloudctl/orgs.yaml
```

---

## Command Reference: Before & After

### Authentication
```bash
# Before
awsctl login bt-avm

# After
cloudctl login bt-avm
```

### Context Switching
```bash
# Before
awsctl switch bt-avm --account 123456789012 --role Admin

# After
cloudctl switch bt-avm --account 123456789012 --role Admin
```

### View Current Context
```bash
# Before
awsctl env
awsctl status

# After
cloudctl env
cloudctl status
```

### Logout
```bash
# Before
awsctl logout

# After
cloudctl logout
```

### Run Commands with Credentials
```bash
# Before
awsctl exec --org bt-avm aws s3 ls

# After
cloudctl exec --org bt-avm aws s3 ls
```

### List Accounts
```bash
# Before
awsctl accounts bt-avm

# After
cloudctl accounts bt-avm
```

### System Health Check
```bash
# Before
awsctl doctor

# After
cloudctl doctor
```

### List Organizations
```bash
# Before (not available, use: awsctl org list)
awsctl org list

# After
cloudctl list
cloudctl org list  # Also works
```

---

## Shell Integration Update

### Bash/Zsh

**Before:**
```bash
# In ~/.bashrc or ~/.zshrc
eval "$(awsctl init)"
```

**After:**
```bash
# In ~/.bashrc or ~/.zshrc
eval "$(cloudctl init)"
```

### Fish

**Before:**
```fish
# In ~/.config/fish/config.fish
cloudctl init | source
```

**After:**
```fish
# In ~/.config/fish/config.fish
cloudctl init | source
```

### PowerShell

**Before:**
```powershell
# In $PROFILE
Invoke-Expression "& {$((awsctl init) -split '\r?\n' | Select-Object -First 1)}"
```

**After:**
```powershell
# In $PROFILE
Invoke-Expression "& {$((cloudctl init) -split '\r?\n' | Select-Object -First 1)}"
```

---

## Backwards Compatibility

⚠️ **Breaking Change**: The old `awsctl` command is no longer available. You must use `cloudctl` instead.

If you need to stay on awsctl v3.x:
- See the [v3.1.0 release](https://github.com/anthropics/cloudctl/releases/tag/v3.1.0) for the old version
- Installation: `pip install awsctl==3.1.0`

---

## Troubleshooting

### "cloudctl: command not found"
1. Verify installation: `pip show cloudctl`
2. Reload shell: `exec $SHELL` or open a new terminal
3. Verify PATH: `which cloudctl`

### "Configuration not found"
If cloudctl doesn't see your organizations:
1. Run `cloudctl doctor` to verify paths
2. Check `~/.cloudctl/` exists (created by `cloudctl init`)
3. Migrate old config: `cp -r ~/.config/awsctl/* ~/.config/cloudctl/`

### "Old ~/.awsctl/ still exists"
The old directory is safe to delete once you've migrated:
```bash
rm -rf ~/.awsctl/
```

---

## Support

- **GitHub Issues**: Report bugs at [cloudctl/issues](https://github.com/anthropics/cloudctl/issues)
- **Documentation**: See [README.md](README.md) for full documentation
- **Troubleshooting**: Run `cloudctl doctor` for system diagnostics

---

## What's New in v4.0.0

### Enhanced Multi-Cloud Support
- Full parity across AWS, Azure, and GCP
- Unified context management for all cloud providers
- Consistent CLI interface across clouds

### Better Name
- `cloudctl` reflects true multi-cloud nature
- Clearer brand positioning
- Easier to discover and remember

### Breaking Changes
- **Command name**: `awsctl` → `cloudctl`
- **Config paths**: `~/.awsctl/` → `~/.cloudctl/`
- **Package name**: `awsctl` → `cloudctl`

### Improvements
- Updated documentation for multi-cloud features
- Enhanced error messages
- Better migration detection

---

## FAQ

**Q: Do I need to re-authenticate?**
A: No, your SSO tokens are cached separately. However, you may need to re-authenticate if your token has expired.

**Q: Will my organization config transfer automatically?**
A: cloudctl will attempt to detect old configurations. Use `cloudctl doctor` to check.

**Q: Can I have both awsctl and cloudctl installed?**
A: Not recommended. Uninstall awsctl v3.x before installing cloudctl v4.0.0.

**Q: What about my shell configuration?**
A: Update your shell profile to use `cloudctl init` instead of `awsctl init`.

**Q: Is this stable?**
A: Yes, v4.0.0 is stable. It's the same codebase as v3.1.0 with the name changed.

---

## Need Help?

1. Check this migration guide
2. Run `cloudctl doctor` for diagnostics
3. See [README.md](README.md) for comprehensive documentation
4. File an issue on [GitHub](https://github.com/anthropics/cloudctl/issues)

