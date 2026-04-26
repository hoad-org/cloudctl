# file: docs/SECURITY_APPRAISAL.md
# Security Appraisal & Risk Assessment

**System:** `cloudctl` (Workstation CLI)
**Version:** 2.8.1 (Enterprise Ready)
**Date:** 2025-12-10
**Classification:** Public / Open Source
**Audience:** CISO, Application Security, Risk & Compliance

---

# 1. Executive Summary

`cloudctl` is a high-assurance command-line interface designed to broker access to AWS IAM Identity Center (SSO).
It operates under a **Zero Trust** philosophy, assuming the developer workstation is a potentially hostile environment.
This appraisal validates the tool's transition to a **"Secure by Default"** architecture (Phase 2).

**Verdict:** **Low Residual Risk** / **Approved for Production**

---

# 2. Threat Landscape

## 2.1 Assets & Data Class

| Asset | Classification | Protection |
| :--- | :--- | :--- |
| **User Identity** | High | Delegated to IdP (Okta/AWS). |
| **Federation Tokens** | Critical | Cached in `~/.aws/sso/cache` (0600 permissions). |
| **Role Credentials** | Critical | In-Memory Only. Never written to disk. |
| **Audit Logs** | Medium | Local file (`audit.log`). |
| **Registry Policy** | High | Administrative Verification (Pilot). Signed via Minisign (Future). |

## 2.2 Threat Actors

| Actor | Capability | Motivation |
| :--- | :--- | :--- |
| **Malicious Developer** | Modify local config, bypass guardrails. | Access prohibited regions/roles. |
| **External Attacker** | Phishing, Token Theft. | Privilege Escalation. |
| **Malware (User Space)** | Read env vars, scrape disk. | Credential Exfiltration. |
| **Insider Threat** | Modify plugins or registry. | Disable logging/security controls. |

## 2.3 Attack Surface Analysis

* **Shell Execution:** The wrapper is the primary boundary. It must resist manipulation and fail closed.
* **Registry Loading:** Vulnerable to SSRF or "Zip Bombs" if unchecked. Mitigated by strict size limits and HTTPS enforcement.
* **Plugins:** Arbitrary Code Execution risk. Mitigated by strict namespace allowlisting (`cloudctl.plugins.*`) and thread isolation.
* **SSO Token Cache:** Risk of token reuse. Mitigated by expiry validation and file permission checks.

---

# 3. Vulnerability Mitigation

## 3.1 Injection Attacks (Arbitrary Code Execution)

### Vector: Shell Injection via Exports
* **Threat:** Injecting shell metacharacters into Role names or Regions.
* **Mitigation:** **Strict Sanitization**. All exported variables are wrapped in `shlex.quote()`.
* **Status:** Verified (Tests: `test_use_exports.py`).

### Vector: Log Injection
* **Threat:** Injecting newlines into "Break Glass" justification to spoof audit logs.
* **Mitigation:** Input sanitization strips control characters and newlines.
* **Status:** Verified (Tests: `test_guardrails.py`).

## 3.2 Information Disclosure

### Vector: Stdout/Stderr Leaks
* **Threat:** Uncaught exceptions printing raw JSON credentials to the screen.
* **Mitigation:** **Auto-Redaction**. The `_aws_json` wrapper catches decoding errors and suppresses raw output.
* **Status:** Verified.

### Vector: TTY Exposure
* **Threat:** Running the binary directly (`_cloudctl_bin`) dumps credentials to history.
* **Mitigation:** **TTY Guard**. The binary detects interactive usage and refuses to print secrets.
* **Status:** Verified.

## 3.3 Integrity & Supply Chain

### Vector: Registry Tampering (Trust Downgrade)
* **Threat:** Attacker modifies `orgs.yaml` to point to a malicious registry or relax guardrails.
* **Mitigation:**
    * **Pilot Phase:** **Administrative Control**. Integrity relies on users correctly copying the approved configuration from the Confluence Source of Truth.
    * **Future State:** **Pinned Trust Anchor**. The client will enforce cryptographic signatures for remote registry updates.
* **Status:** Process Control Verified (v2.8.1).

---

# 4. Operational Security

## 4.1 Deployment Governance
* **Distribution:** `cloudctl` is distributed via tagged `git` releases installed via `pipx`.
* **Updates:** The `min_client_version` registry field forces client upgrades.

## 4.2 Logging & Audit
* **Local:** "Break Glass" events are logged to `~/.cloudctl/audit.log`.
* **Remote:** AWS CloudTrail captures all `AssumeRole` events.

---

# 5. Conclusion

`cloudctl` v2.8.1 demonstrates a mature security posture. By systematically addressing injection, leakage, and integrity risks, it exceeds the baseline requirements for a privileged developer utility.
