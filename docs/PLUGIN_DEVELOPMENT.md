# file: docs/PLUGIN_DEVELOPMENT.md
# Plugin Development Guide

Plugins allow platform and security teams to add **organization-wide checks** that run automatically before AWS SSO login.

---

## 1. Plugin Requirements (v2.7.0+)

### 1.1 Namespace Restriction 🛡️

To prevent Arbitrary Code Execution (ACE), `awsctl` now enforces strict namespace checking.
Your plugin module **MUST** start with one of the following prefixes:

* `awsctl.plugins.`
* `myorg.plugins.` (Replace `myorg` with your organization's internal package namespace)

Plugins trying to load from other namespaces (e.g., `os`, `subprocess`, `requests`) via `orgs.yaml` will be blocked with a security error.

### 1.2 Structure

A plugin is a Python module that exposes a `pre_login` function.

    # myorg/plugins/vpn_check.py
    import sys
    from typing import Any, Dict

    def pre_login(org: Dict[str, Any]) -> None:
        """
        Hook executed before AWS SSO login starts.
        """
        print(f"Running VPN check for {org['name']}...")

        if not _is_vpn_connected():
            print("✗ VPN Connection NOT detected.", file=sys.stderr)
            sys.exit(1)  # Abort login

---

## 2. Configuration

### 2.1 Enforced Plugins (Registry)

Defined in `src/awsctl/registry.py` (or the **Remote Registry** if Tier 3 is configured). Users cannot disable these.

    "plugins": ["awsctl.plugins.okta"]

### 2.2 Optional Plugins (User Config)

Enabled by end-users in `~/.awsctl/orgs.yaml`.

    plugins:
      enabled:
        - myorg.plugins.dev_tools

---

## 3. Best Practices

- **Fail Safe:** If your plugin crashes, `awsctl` fails closed (aborts login).
- **No Side Effects:** Do not modify credentials directly.
- **Fast Execution:** Plugins run synchronously in the critical path and must complete within **10 seconds**, otherwise they will be terminated.
