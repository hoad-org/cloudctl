# file: docs/SECURITY_APPRAISAL.md
# Security Appraisal & Risk Assessment

**System:** `awsctl` (Workstation CLI)
**Version:** 2.7.0 (Enterprise Ready)
**Date:** 2025-12-08
**Classification:** Public / Open Source
**Audience:** CISO, Application Security, Risk & Compliance

---

# 1. Executive Summary

`awsctl` is a high-assurance command-line interface designed to broker access to AWS IAM Identity Center (SSO).
It operates under a **Zero Trust** philosophy, assuming the developer workstation is a potentially hostile environment.
This appraisal validates the tool's transition to a **"Secure by Default"** architecture.
Following a forensic audit, significant engineering effort was applied to neutralize classes of vulnerabilities including Arbitrary Code Execution (ACE), Credential Leakage, and Privilege Escalation.

**Verdict:** **Low Residual Risk** / **Approved for Production**

---

# 2. Architecture & Trust Model

## 2.1 The "Context Bridge" Shell Integration
The core security mechanism is the isolation of the Python process from the user's shell environment.
* **Mechanism:** `awsctl` functions as a shell wrapper that evaluates (`eval`) a sanitized payload emitted by a hidden binary (`_awsctl_bin`).
* **Security Benefit:** This allows **Ephemeral Credential injection** (STS tokens) directly into process memory without ever writing long-term Access Keys (`AKIA...`) or Secret Keys to disk.
* **Attack Surface Reduction:** By avoiding `~/.aws/credentials`, the tool neutralizes standard malware exfiltration vectors (e.g., info-stealers designed to scrape static credential files).

## 2.2 Registry-Backed Hydration (Immutable Policy)
Configuration is not trusted from the user. It is **hydrated** from a central authority.
* **Tier 1 (Embedded):** Compiled internal Registry (`src/awsctl/registry.py`).
* **Tier 3 (Remote GitOps):** Loaded from a remote HTTPS endpoint, protected by **Minisign** cryptographic verification.
* **Control:** **Input Validation & Sanitization**.
* **Enforcement:** Users cannot locally override security boundaries (Allowed Regions, SSO URLs, Preferred Roles).
* **Integrity:** The Registry acts as the **Root of Trust** for all authorization decisions.
  Changes to policy require a code deployment or a signed artifact update.

---

# 3. Threat Modeling & Vulnerability Mitigation

This section details specific attack vectors and the implemented controls (v2.2 baseline + v2.5 enhancements).

## 3.1 Injection Attacks (Arbitrary Code Execution)

### Vector: Shell Injection via Environment Exports
* **Threat:** A malicious actor (or compromised upstream API) injects shell metacharacters (e.g., `; rm -rf /`) into AWS Role names or Region strings.
* **Mitigation:** **Strict Output Sanitization**.
    * All exported variables (`AWS_ACCESS_KEY_ID`, `AWS_REGION`, etc.) are wrapped in `shlex.quote()` before emission.
* **Status:** Verified (IDs `PYBH-0016`, `PYBH-0025`).

### Vector: Config Section Injection
* **Threat:** Malicious inputs in Organization names could corrupt the `~/.aws/config` INI parser, potentially injecting rogue profiles or settings.
* **Mitigation:** **Input Sanitization**.
    * Organization names are sanitized to alphanumeric characters before being used as INI section headers.
* **Status:** Verified (ID `PYBH-0138`).

### Vector: Log Injection (New in v2.5)
* **Threat:** A user injects newlines or control characters into the "Break Glass" justification prompt to spoof audit log entries.
* **Mitigation:** **Input Sanitization**.
    * The justification string is stripped of newlines (`\n`, `\r`) and Unicode control characters before writing to the audit log.
* **Status:** Verified (ID `PYBH-0030`).

## 3.2 Information Disclosure (Credential Leakage)

### Vector: Stdout/Stderr Leaks
* **Threat:** An uncaught exception or verbose logging during a crash prints raw STS credentials (Session Tokens) to the terminal or CI/CD logs.
* **Mitigation:** **Targeted Redaction & Fail-Closed Logic**.
    * **Redaction:** A custom `stderr` formatter intercepts arguments matching sensitive flags (`--access-token`, `sessionToken`) and replaces values with `[REDACTED]`.
* **Fail-Closed Wrapper:** The shell integration verifies the execution strategy *before* running.
    If the strategy check fails, the wrapper aborts immediately, preventing accidental payload execution that would print secrets to history.
* **Status:** Verified (IDs `PYBH-0063`, `PYBH-0116`, `PYBH-0111`).

### Vector: TTY Exposure (Shoulder Surfing)
* **Threat:** A user accidentally runs the internal binary (`_awsctl_bin switch`) directly, dumping credentials to the screen.
* **Mitigation:** **TTY Detection Guard**.
    * The application detects if `stdout` is attached to an interactive terminal during export operations.
    If true, it terminates execution with a security violation.
    * **Exception:** The `awsctl env` command explicitly bypasses this check *only* if output is piped or redirected (Smart Pipe Detection).

## 3.3 Privilege Escalation & Integrity

### Vector: Unauthorized High-Privilege Access (New in v2.5)
* **Threat:** A developer uses `AdministratorAccess` for routine tasks, increasing the blast radius of a compromised workstation.
* **Mitigation:** **Break Glass Audit (Just-In-Time Justification)**.
    * Roles tagged as `sensitive_roles` in the Registry trigger a mandatory interactive prompt asking for a justification (Ticket ID/Reason).
    * Access is denied if the user aborts the prompt.
    * **Status:** Verified (Feature #3).

### Vector: Race Conditions (TOCTOU) on Config Files
* **Threat:** A local attacker exploits the time gap between file creation and permission setting to read sensitive configuration (`orgs.yaml`).
* **Mitigation:** **Atomic Writes with Restricted Permissions**.
    * Files are written to a temporary location.
    * `os.chmod(0o600)` is applied *before* the file content is flushed or the file is moved.
    * `os.replace` is used for atomic swap, eliminating the race window.
    * **Status:** Verified (IDs `PYBH-0090`, `PYBH-0096`, `PYBH-0113`).

### Vector: Root Ownership Hijack
* **Threat:** Running `sudo awsctl setup` changes ownership of the user's `~/.bashrc` to `root`, causing a Denial of Service on the user's shell login.
* **Mitigation:** **UID/GID Preservation**.
    * The setup routine detects `SUDO_UID` / `SUDO_GID` and drops privileges or explicitly sets file ownership to the original user.
* **Status:** Verified (ID `PYBH-0089`).

## 3.4 Availability & Denial of Service

### Vector: Remote Registry "Zip Bomb" / DoS (New in v2.5)
* **Threat:** An attacker compromises the Remote Registry URL and serves a multi-gigabyte file, causing OOM crashes on developer machines.
* **Mitigation:** **Streaming Limits & Chunked Reads**.
    * The remote loader enforces a strict `1MB` limit on download size and a `10MB` limit on decompression size.
* **Status:** Verified (ID `PYBH-0062`).

### Vector: Infinite Loops (API Thrashing)
* **Threat:** Malformed responses from AWS APIs cause the pagination logic to loop indefinitely, consuming CPU/Network.
* **Mitigation:** **Circuit Breakers**.
    * Listing logic enforces a hard cap (100 pages) on pagination loops.
* **Status:** Verified (ID `PYBH-0140`).

### Vector: Thread Deadlocks
* **Threat:** Unsafe subprocess calls (`preexec_fn`) in multithreaded UI contexts (spinners) cause the CLI to hang.
* **Mitigation:** **Thread-Safe Subprocess Management**.
    * Replaced `preexec_fn` with `start_new_session=True` parameter.
    * **Status:** Verified (IDs `PYBH-0056`, `PYBH-0101`).

## 3.5 Supply Chain & Build Integrity

### Vector: Remote Configuration Tampering (New in v2.5)
* **Threat:** An attacker compromises the S3 bucket hosting the Remote Registry JSON.
* **Control:** **Cryptographic Signature Verification (Minisign)**.
    * The client verifies the `registry.json` against `registry.json.minisig` using a locally configured Public Key.
    * If verification fails, the update is rejected, and the client falls back to the embedded safe defaults.
    * **Status:** Verified (Feature #4).

### Vector: Dependency Poisoning
* **Threat:** A malicious package is introduced into the dependency tree (e.g., typosquatting).
* **Control:** **Dependency Locking & Auditing**.
    * Runtime dependencies are strictly pinned in `pyproject.toml` (specifically `urllib3>=2.2.2`).
    * `pip-audit` runs on every CI build to detect known CVEs.
    * **Status:** Active in GitHub Actions.

### Vector: Tampered Distribution
* **Threat:** An attacker modifies the code between source control and the user's machine.
* **Control:** **Signed Tags & Pipx Isolation**.
    * Releases are tied to Git tags (`v2.7.0`).
    * Installation via `pipx` ensures the tool runs in an isolated Virtual Environment, preventing interference from system-wide Python packages.

## 3.6 Data Residency & Forensics

* **Disk:** Zero long-term keys are written to disk.
* **Audit Logs:** "Break Glass" justifications are stored in `~/.awsctl/audit.log`. This file is rotated at 5MB to prevent disk exhaustion.
* **Tokens:** The only persistence is the AWS CLI v2 SSO cache (`~/.aws/sso/cache`), protected by `0600` permissions.
* **Memory:** STS credentials exist in the shell process memory.
* **Residual Risk (Swap):** If the OS pages RAM to disk (swap), credentials could theoretically be recovered forensically.
  This is an OS-level risk inherent to all CLI tools.
    * **Mitigation:** Corporate endpoints should enforce Full Disk Encryption (BitLocker/FileVault).

---

# 4. Operational Security

## 4.1 Deployment Governance
* **Distribution:** `awsctl` is distributed via tagged `git` releases installed via `pipx`.
* **Updates:** The `min_client_version` field in the Registry allows admins to forcibly block logins from outdated clients.
* **Integrity:** `awsctl doctor` validates installation integrity.

## 4.2 Logging & Audit
* **Local:** "Break Glass" events are logged to `~/.awsctl/audit.log` (Rotation enabled).
  Debug logs (`--debug`) output to `stderr` and are transient.
* **Remote:** All AWS actions initiated by the tool (login, assume role) generate standard **AWS CloudTrail** events (`AssumeRole`, `ConsoleLogin`), ensuring full attributability to the user identity.

---

# 5. Assurance Evidence

The security posture is validated through automated testing gates enforced in CI/CD.

| Control Area | Validation Mechanism | Status |
| :--- | :--- | :--- |
| **Supply Chain** | `pip-audit` scans dependency tree for CVEs on every build. | ✅ **PASSED** |
| **Static Analysis** | `bandit` scans for shell injection (`B603`) and assert misuse (`B101`). | ✅ **PASSED** |
| **Credential Safety** | `tests/test_use_exports.py` mocks TTY presence and asserts `SystemExit(1)`. | ✅ **PASSED** |
| **Integrity** | `tests/test_shell.py` validates fail-closed wrapper logic. | ✅ **PASSED** |
| **Isolation** | `tests/test_cli_coverage_boost.py` confirms environment sanitization. | ✅ **PASSED** |
| **Break Glass** | `tools/comprehensive_smoke.sh` validates interactive prompt interception. | ✅ **PASSED** |
| **Remote Integrity** | `tests/test_registry_loader.py` validates Minisign signature rejection. | ✅ **PASSED** |

---

# Appendix A: Compliance Mapping

Mapping `awsctl` controls to common security frameworks:

| Framework | Control ID | Requirement | awsctl Implementation |
| :--- | :--- | :--- | :--- |
| **NIST 800-53** | **AC-3** | Access Enforcement | Enforces Registry-defined RBAC and Region restrictions at the CLI level. |
| **NIST 800-53** | **IA-2** | Identification & Authentication | Delegates auth to AWS Identity Center (MFA/SSO) via browser integration. |
| **SOC2** | **CC6.1** | Logical Access Security | Prevents usage of long-term static keys; enforces least privilege via "Preferred Roles". |
| **SOC2** | **CC6.8** | Preventing Unauthorized Software | "Min Client Version" enforcement ensures only compliant versions access the cloud. |
| **PCI DSS** | **7.1** | Limit Access to Cardholder Data | "Region Guardrails" ensure developers cannot accidentally access PCI scopes (e.g., Prod) without explicit authorization. |
| **PCI DSS** | **10.2** | Audit Trails | "Break Glass" creates a local audit trail for high-privilege access. |

---

# 6. Conclusion

`awsctl` v2.7.0 demonstrates a mature security posture. By systematically addressing the identified findings—specifically around injection, leakage, and file integrity—and adding Enterprise Governance features (Remote Registry, Break Glass), the tool now exceeds the baseline requirements for a privileged developer utility.
The architecture effectively balances **Developer Experience** (speed, usability) with **Strict Isolation**, ensuring that the organization maintains governance over cloud access without hindering productivity.
