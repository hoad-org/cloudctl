# file: docs/PLUGIN_DEVELOPMENT.md
# Plugin Framework — awsctl v2.8.1

Plugins allow enforcement of corporate posture (e.g., VPN check, device compliance) before login.

## 1. Requirements

### 1.1 Namespace Restriction

For security, plugins must be importable via the protected namespace:

> awsctl.plugins.<name>

### 1.2 Exposed Function

The module must define:

> def pre_login(org: dict) -> None:
>     ...

### 1.3 Execution Model

**Threaded:** Runs in a separate thread to prevent blocking the UI loop indefinitely.

**Timeout:** Hard limit of 10 seconds. (Best practice: keep under 3 seconds).

**Fail-Closed:** Uncaught exceptions or timeouts abort the login process.

## 2. Best Practices

**No Side Effects:** Do not modify the org dictionary or global state.

**StdErr Reporting:** Print user-facing errors to `sys.stderr` using `console.print`.

**Exit Codes:** Use `sys.exit(1)` to signal a check failure (e.g., VPN disconnected).
