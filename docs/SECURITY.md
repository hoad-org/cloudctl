# file: docs/SECURITY.md
# Security Policy

**Version:** 2.7.0

## 🛡️ Trust Model & Architecture

`awsctl` is designed with a **Zero Trust** philosophy for developer workstations.
It adheres to the following core security tenets:

1.  **Ephemeral Credentials:** No long-term AWS Access Keys (`AKIA...`) are ever written to disk.
2.  **Registry-Backed Policy:** Guardrails (Regions, Roles, Plugins) are defined centrally and cannot be overridden by local user configuration.
    This Registry is either **Embedded** (Tier 1) or **Remote & Signed** (Tier 3).
3.  **Least Privilege:** Users are guided toward `preferred_roles` defined in the registry.
4.  **Secure Execution:** Shell integration uses a "Context Bridge" strategy (`eval`/`exec`) protected by strict output isolation.
    The wrapper **fails closed** if the binary returns unexpected output.
5.  **Plugin Sandboxing:** Plugins are restricted to the `awsctl.plugins.*` or `myorg.plugins.*` namespaces to prevent Arbitrary Code Execution via configuration tampering.
6.  **Cryptographic Integrity:** Remote configurations (Tier 3) are verified against offline signatures (Minisign) before loading.

---

## 📦 Supported Versions

Only the latest semantic version is supported.
We encourage all users to pin their installation to a specific tag but update frequently.

| Version | Supported          |
| ------- | ------------------ |
| 2.7.x   | :white_check_mark: |
| < 2.7   | :x:                |

---

## 🐛 Reporting a Vulnerability

If you discover a security vulnerability in `awsctl`, please **DO NOT** open a public issue.

### Reporting Process

1.  Email the security team at **[choad@beyondtrust.com]** (or page the Cloud Platform on-call).
2.  Include "SECURITY" in the subject line.
3.  Provide a reproduction script or description of the bypass.

### Critical Vectors (In Scope)

We are particularly interested in reports regarding:

* **Guardrail Bypasses:** Circumventing region or role restrictions enforced by the Registry.
* **Plugin Evasion:** Logging in without triggering mandatory plugins (e.g., VPN check).
* **Credential Leakage:** Scenarios where credentials persist in shell history, logs, or disk.
* **Namespace Bypass:** Trick the plugin loader into importing system modules (e.g., `os`, `subprocess`) via `orgs.yaml`.
* **TTY Guard Bypass:** Tricking the binary into dumping credentials to a non-interactive stream.
* **Signature Bypass:** Forcing the client to load a tampered Remote Registry without a valid Minisign signature.
* **Audit Evasion:** Bypassing the "Break Glass" justification prompt for sensitive roles.

### Out of Scope

The following are considered part of the accepted threat model and are **not** vulnerabilities:

* **Physical Access:** If an attacker has physical access to an unlocked workstation.
* **Root/Admin Compromise:** If an attacker already has root/sudo access to the machine, they can dump process memory.
  `awsctl` protects against *user-space* accidents and malware, not kernel-level compromise.
* **AWS API Latency:** Denial of service due to AWS availability.

---

## 🚨 Incident Response

1.  **Triage:** We aim to acknowledge reports within 24 hours.
2.  **Fix:** Critical vulnerabilities will be patched in a hotfix release (e.g., `v2.7.1`).
3.  **Disclosure:** After the patch is released and adopted, we will publish a security advisory.
