# Plugin Development Guide

This document explains how to extend `awsctl` with custom plugins.  
Plugins allow platform and security teams to add **organization-wide checks and workflows** that run automatically before AWS SSO login and context selection, without forking the core `awsctl` logic.

---

## 1. Plugin Model Overview

`awsctl` supports two broad categories of plugins:

1. **Enforced Plugins (Registry)**
   - Defined in `src/awsctl/registry.py` per organization.
   - Cannot be disabled by end-users.
   - Intended for security-critical checks (VPN, device posture, Okta, MFA).

2. **Optional Plugins (User Config)**
   - Enabled by end-users in `~/.awsctl/orgs.yaml` under `plugins.enabled`.
   - Typically used for quality-of-life or team-specific enhancements.

All plugins are standard Python modules importable by name.

---

## 2. Where Plugins Are Configured

### 2.1 Registry (Enforced Plugins)

Configured centrally per org:

    # src/awsctl/registry.py

    KNOWN_ORGS = [
        {
            "name": "engineering",
            "plugins": ["awsctl.plugins.okta"],
            # ...
        },
        # ...
    ]

These plugins are:

- Loaded whenever the corresponding org is used.
- Executed before login.
- Not removable or bypassable by users.

---

### 2.2 User Config (Optional Plugins)

Users can opt-in to additional plugins:

    # ~/.awsctl/orgs.yaml

    enabled_orgs:
      - engineering

    plugins:
      enabled:
        - awsctl.plugins.okta
        - myorg.awsctl.plugins.dev_tools

Note: The loader handles deduplication if a plugin is listed in both places.

---

## 3. Plugin Lifecycle

1. `awsctl` determines the active organization.
2. It builds a combined plugin list from the Registry and User Config.
3. It imports each module by name.
4. It calls the `pre_login` hook.
5. If any plugin signals failure (for example, exits with non-zero), the operation is aborted.

---

## 4. Writing a Plugin

### 4.1 Basic Structure

A plugin is simply a Python module.  
It must expose a function named `pre_login`.

Example:

    # myorg/awsctl/plugins/vpn_check.py
    import sys
    from typing import Any, Dict


    def pre_login(org: Dict[str, Any]) -> None:
        """
        Hook executed before AWS SSO login starts.

        Args:
            org: The hydrated organization configuration dictionary
                 (contains name, start_url, allowed_regions, etc.)
        """
        print(f"Running checks for {org['name']}...")

        if not _is_vpn_connected():
            print("✗ VPN Connection NOT detected.", file=sys.stderr)
            sys.exit(1)  # Abort login


    def _is_vpn_connected() -> bool:
        # ... implementation details ...
        return True

---

### 4.2 Logging and Error Reporting

- **Success:** Print informational messages to stdout.
- **Failure:** Print concise, human-readable errors to stderr and call `sys.exit(1)`.
- **Debug:** Use standard Python logging or `print` if additional diagnostics are needed.

---

## 5. Deployment

Plugins must be importable by the Python environment running `awsctl`.

### Option A: Built-in (Pull Request)

- Submit your plugin to the `src/awsctl/plugins/` directory in this repository.
- Best for organization-standard plugins.

### Option B: External Package

- Package your plugin as a separate Python library (for example, `my-awsctl-plugins`) and install it into the `awsctl` environment.

If installed via `pipx`:

    pipx inject awsctl my-awsctl-plugins

---

## 6. Example: The Okta Plugin

The bundled `awsctl.plugins.okta` plugin serves as the reference implementation.

Source: `src/awsctl/plugins/okta.py`

What it does:

- Validates that `start_url` is present in the org config.
- Performs a HEAD request to the URL to ensure connectivity (for example, verifying corporate network access).
- Exits with status `1` if the URL is unreachable.

---

## 7. Best Practices

- **Keep it Fast:** Plugins run synchronously in the critical path. Avoid heavy computations or long network waits.
- **Idempotent:** Plugins should be safe to run multiple times without side effects.
- **No Side Effects:** Do not modify `~/.aws/config` or credentials directly; let `awsctl` and the AWS CLI handle that.
- **Fail Safe:**  
  If your plugin crashes with an unhandled exception, `awsctl` will catch it and abort the login to prevent insecure access.  
  Always prefer failing closed over failing open.
