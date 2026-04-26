# Credential Refresh Strategy Analysis

**Question:** Should cloudctl automatically handle credential refresh instead of delegating to provider CLIs?

**Short Answer:** ❌ Not a good idea for security/design reasons, BUT ✅ we can improve the UX

---

## Why NOT to Build Refresh Into cloudctl

### 1. 🔐 Security - Don't Reimplement Auth

**Current Design (Good):**
```
cloudctl → delegates to → gcloud auth login
                     → aws sso login
                     → az login
         (each provider handles OAuth/SAML securely)
```

**If We Built It Into cloudctl:**
```
cloudctl → needs to → implement OAuth flow
                  → handle SAML
                  → manage browser interactions
                  → store temp secrets
                  → validate tokens
```

**Risk:** cloudctl would become a crypto-handling library. Provider teams are better at this.

### 2. 🎯 Design Principle - Do One Thing Well

cloudctl's stated goal:
> "Use native AWS/Azure/GCP components, ensuring compatibility, reliability, and security"

Building auth into cloudctl violates this:
- ❌ Reimplements what providers already do
- ❌ Harder to maintain (3 auth systems = 3x bugs)
- ❌ Breaks when provider auth changes
- ❌ More code = more attack surface

### 3. 🔄 Provider Updates

When AWS adds MFA requirements or Google changes OAuth flow:
- ✅ With delegated approach: Users get fix automatically (via `aws` CLI or `gcloud` update)
- ❌ With built-in approach: cloudctl needs code update + release + user installation

### 4. 🖥️ Browser Interaction

OAuth login requires browser for:
- User entering credentials
- 2FA challenges
- Consent screens

cloudctl would need to:
- Detect OS (macOS/Linux/Windows)
- Open appropriate browser
- Handle `localhost:PORT` callback
- Parse response
- ❌ Much complexity, many edge cases

### 5. 🏢 Enterprise Scenarios

Some organizations use:
- Hardware security keys (FIDO2)
- SAML via Okta/Azure AD federation
- Custom MFA flows
- Device certificate auth

cloudctl can't handle all of these—providers' native CLIs can.

---

## Better Alternative: Smart Refresh Detection

Instead of building auth, we can improve UX with **intelligent error handling**:

### Option 1: Pre-flight Validation (Recommended)

```python
# Before switching context, check if credentials are valid

def cmd_switch(org_name, account, role, region):
    """Switch context with credential validation"""
    
    # 1. Load requested org
    org = config.get_org(org_name)
    provider = get_provider(org)
    
    # 2. Validate credentials are not expired
    if not provider.is_authenticated(org):
        console.print(f"[red]Credentials expired for {org_name}[/]")
        console.print(f"\nRun to refresh:")
        
        if org.get("provider") == "gcp":
            console.print("  gcloud auth login")
            console.print("  gcloud auth application-default login")
        elif org.get("provider") == "aws":
            console.print("  cloudctl login myorg")
        else:
            console.print("  az login")
        
        return 1
    
    # 3. If valid, proceed with context switch
    context_manager.save_context(org, account, role, region)
    return 0
```

**Benefits:**
- ✅ Fast failure (detect early)
- ✅ Clear messaging
- ✅ No security risk
- ✅ Easy to implement

### Option 2: Shell Wrapper Auto-Refresh

```bash
# In ~/.bashrc or ~/.zshrc (cloudctl shell wrapper)

cloudctl_switch() {
    local org="$1" account="$2" role="$3"
    
    # Check if we need to refresh
    if ! $(_cloudctl_bin test-auth "$org"); then
        echo "Refreshing credentials for $org..."
        
        case "$org" in
            *gcp*)
                gcloud auth login
                gcloud auth application-default login
                ;;
            *azure*)
                az login
                ;;
            *)
                cloudctl login "$org"
                ;;
        esac
    fi
    
    # Now switch
    cloudctl switch "$org" "$account" "$role"
}
```

**Benefits:**
- ✅ Transparent to user
- ✅ Still delegates to provider CLI
- ✅ Works in shell environment
- ✅ Can run async (don't block)

### Option 3: Scheduled Background Refresh

```python
# Periodically check if any credentials are about to expire

import schedule
import time
from threading import Thread

def refresh_all_credentials():
    """Refresh credentials before they expire"""
    for org in config.load_orgs_config():
        provider = get_provider(org)
        
        # Check if expiring in next 30 minutes
        if provider.expires_in_seconds(org) < 1800:
            console.print(f"Refreshing {org['name']}...")
            provider.login(org)

# Schedule to run every hour
schedule.every(1).hours.do(refresh_all_credentials)

# Run in background thread
Thread(target=lambda: schedule.run_pending(), daemon=True).start()
```

**Benefits:**
- ✅ Proactive (refresh before expiration)
- ✅ User doesn't wait
- ✅ Still uses provider CLI
- ✅ Background task

---

## Recommended Implementation

### Phase 1: Pre-flight Validation (Quick Win)

**File to modify:** `src/cloudctl/commands/exec.py`

```python
def pre_flight_check(org: Dict, provider: CloudProvider) -> bool:
    """Validate credentials before execution"""
    
    try:
        # Try to get a token - fails fast if expired
        token = provider.load_token(org)
        if not token:
            return False
        return True
    except Exception:
        return False

def cmd_exec(account, role, region, command):
    org = config.get_org(...)
    provider = get_provider(org)
    
    if not pre_flight_check(org, provider):
        console.print("[red]Credentials expired[/]")
        if org.get("provider") == "gcp":
            console.print("Run: gcloud auth login")
        return 1
    
    # Proceed...
```

**Impact:**
- ✅ 20 lines of code
- ✅ Catches errors early
- ✅ Better UX
- ✅ No security risk

### Phase 2: Helpful Error Messages (Enhancement)

When credentials expire, improve the error message:

**Before:**
```
ERROR: (gcloud.auth.print-access-token) There was a problem 
refreshing your current auth tokens: Reauthentication failed. 
cannot prompt during non-interactive execution.
```

**After (with cloudctl wrapping):**
```
[red]✗ GCP Credentials Expired[/]

Your GCP credentials have expired. To continue:

  $ gcloud auth login
  $ gcloud auth application-default login
  
Then try again:
  
  $ cloudctl switch gcp-org <project> <role>
```

**Benefits:**
- ✅ Clearer guidance
- ✅ Still delegates to provider
- ✅ Works with existing design

### Phase 3: Optional - Auto-Refresh Wrapper (Advanced)

Create optional shell wrapper that auto-refreshes:

```bash
# ~/.config/cloudctl/auto-refresh-wrapper.sh

#!/bin/bash
# Auto-refresh credentials if needed

org="$1"

# Quick check: try to run a simple provider command
case "$org" in
    gcp*)
        if ! gcloud auth print-access-token &>/dev/null; then
            echo "Refreshing GCP credentials..."
            gcloud auth login
        fi
        ;;
    aws*)
        if ! aws sts get-caller-identity &>/dev/null; then
            echo "Refreshing AWS credentials..."
            cloudctl login "$org"
        fi
        ;;
esac

# Proceed with cloudctl
cloudctl switch "$org" "${@:2}"
```

**Benefits:**
- ✅ Optional (users can enable)
- ✅ Still uses provider CLIs
- ✅ Doesn't modify cloudctl core
- ✅ Can be distributed as separate tool

---

## Comparison Table

| Approach | Security | Maintenance | UX | Recommended |
|----------|----------|-------------|-----|-------------|
| **Current (delegate)** | ✅✅✅ | ✅✅✅ | ⚠️ Could improve | Yes |
| **Built-in refresh** | ⚠️ Risk | ❌ Hard | ✅ Good | No |
| **Pre-flight validation** | ✅✅✅ | ✅✅ | ✅ Better | Yes |
| **Smart error messages** | ✅✅✅ | ✅✅✅ | ✅ Better | Yes |
| **Shell wrapper** | ✅✅✅ | ✅✅ | ✅✅ Good | Optional |
| **Background refresh** | ✅✅ | ⚠️ Complex | ✅✅ Good | Future |

---

## Proposed Implementation Plan

### What TO Add
1. ✅ Pre-flight credential validation
2. ✅ Improved error messages showing exact commands
3. ✅ Optional shell wrapper for auto-refresh
4. ✅ Documentation on credential lifecycle

### What NOT to Add
1. ❌ OAuth flow implementation
2. ❌ SAML handling
3. ❌ Token storage (keep delegated)
4. ❌ MFA logic

---

## Code Example: Minimal Pre-flight Check

Here's what we could add (30 lines):

```python
# src/cloudctl/providers/base.py

class CloudProvider(ABC):
    
    def is_authenticated(self, org: Dict[str, Any]) -> bool:
        """
        Quick check: are credentials still valid?
        Returns False if token is expired or missing.
        """
        try:
            token = self.load_token(org)
            if not token:
                return False
            
            # Check if token is expired (provider-specific)
            if hasattr(token, 'expiresAt'):
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                expires = token.expiresAt
                if isinstance(expires, str):
                    expires = datetime.fromisoformat(expires)
                if expires <= now:
                    return False
            
            return True
        except Exception:
            return False
```

Then in the switch/exec commands:

```python
def cmd_switch(org_name, account, role, region):
    org = config.get_org(org_name)
    provider = get_provider(org)
    
    # Quick pre-flight check
    if not provider.is_authenticated(org):
        console.print(f"[red]Credentials expired[/] for {org_name}")
        console.print(f"\n[yellow]To refresh, run:[/]")
        
        provider_name = org.get("provider", "aws")
        if provider_name == "gcp":
            console.print("  gcloud auth login")
            console.print("  gcloud auth application-default login")
        elif provider_name == "aws":
            console.print(f"  cloudctl login {org_name}")
        else:
            console.print("  az login")
        
        return 1
    
    # Proceed with context switch
    return _do_switch(org, account, role, region)
```

**Result:** Better UX, zero security risk, minimal code.

---

## Conclusion

### ❌ Don't Build Auth Into cloudctl

- ❌ Duplicates provider functionality
- ❌ Security risk (reimplemented crypto)
- ❌ Maintenance nightmare
- ❌ Breaks with provider updates

### ✅ Do Improve Detection & Messaging

- ✅ Pre-flight credential validation
- ✅ Clear, actionable error messages
- ✅ Optional shell wrapper for automation
- ✅ Leverage native provider CLIs

**The key insight:** cloudctl's strength is that it **delegates properly**. Don't weaken that.

---

**Recommendation:** Implement Phase 1 (pre-flight validation) for better UX while preserving the security-first design.
