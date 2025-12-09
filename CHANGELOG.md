## [2.7.0] - 2025-12-08

### 🛡️ Critical Security & Stability
This release addresses a critical regression in shell integration and hardens the Zero Trust architecture.

* **Fix:** Solved "Smart Login Chain" failure where credentials were printed to stdout instead of being evaluated by the shell.
* **Fix:** Hardened `awsctl env` command to ensure reliable POSIX export generation.
* **Security:** Enhanced TTY Guard to prevent accidental credential leakage in non-interactive sessions.
* **UX:** Moved "Advanced Execution" features to a stable command structure.

### 🚀 Enterprise Governance & Usability (v2.6.0)
This release bridges the gap between strict security compliance and developer velocity with "Smart History" and "Break Glass" workflows.
* **Remote Registry (GitOps):** `awsctl` can now load its configuration and guardrails from a cryptographically signed remote JSON file (via HTTPS/S3).
  This allows Platform Teams to update policies instantly without forcing a binary rebuild.
* **Break Glass Audit:** Accessing sensitive roles (configured in the Registry, e.g., `AdministratorAccess`) now triggers a mandatory interactive prompt requiring a justification.
  This is logged locally to `~/.awsctl/audit.log` for compliance.
* **Smart History:** The context selector now remembers your last 5 used accounts/roles and displays them at the top of the list with a `🕒` icon for instant access.
* **Quick Switch Aliases:** Added support for user-defined aliases in `orgs.yaml`.
  You can now switch contexts instantly using `awsctl switch @prod-db`.
* **Minimum Version Enforcement:** The Registry can now enforce a `min_client_version`.
  Older clients will be blocked from logging in until they upgrade.

### 🛡️ Security Improvements
* **DoS Protection (Zip Bomb):** The remote registry loader implements strict streaming limits (1MB download, 10MB expansion) to prevent Out-of-Memory attacks via malicious payloads.
* **Log Injection Prevention:** All user input provided to the "Break Glass" prompt is sanitized (newlines and control characters stripped) before being written to the audit log.
* **Dependency Hardening:** Upgraded `urllib3` to >=2.2.2 to patch CVE-2024-xxxx vulnerabilities.
