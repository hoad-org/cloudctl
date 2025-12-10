# file: docs/SECURITY.md
# Security Policy

**Version:** 2.8.0

## 🛡️ Trust Model

`awsctl` follows a **Zero-Trust** workstation model. We assume the local environment is hostile and prioritize isolation, integrity, and auditability.

### Core Security Tenets

#### 1. Ephemeral Credentials Only

No long-term AWS keys (`AKIA...`) are ever written to disk. All credentials are short-lived STS tokens held in process memory.

#### 2. Registry-Backed Governance

Guardrails (Regions, Roles, Plugins) are defined centrally.

- **Immutable:** Local user configuration cannot override corporate policy.
- **Pinned Trust:** Tier 3 Remote Registries are verified against a hardcoded Public Key, ignoring user config overrides.

#### 3. Shell Wrapper Fail-Closed Strategy

If the wrapper cannot verify the binary’s execution strategy:

- No environment variables are modified.
- No credentials are printed.
- The command fails safely.

#### 4. Plugin Sandboxing

Plugins must:

- Reside under the `awsctl.plugins.*` namespace.
- Execute in an isolated thread with strict timeouts (10s).
- Fail closed (Crash = Login Abort).

#### 5. Cryptographic Integrity (Tier 3)

Signed registries are verified using **Minisign**.

- **Protections:** HTTPS-only, Size caps on streams, Tamper detection.
- **Behavior:** Immediate exit on signature mismatch.

#### 6. Break-Glass Workflow

Sensitive roles (e.g., Admin) require:

- User justification (Interactive Prompt).
- Logged locally to `~/.awsctl/audit.log`.

---

## 📦 Supported Versions

| Version | Support | Status |
| :--- | :--- | :--- |
| **2.8.x** | ✔ Supported | Enterprise Release |
| **2.7.x** | ✔ Supported | Backwards Compatibility |
| **< 2.7** | ❌ Unsupported | Vulnerable (Upgrade Required) |

---

## 🐛 Reporting a Vulnerability

**Do NOT raise a public issue.**

**Contact:**

- Security Team: `choad@beyondtrust.com`
- Cloud Platform On-Call

**Include:**

- Steps to reproduce.
- Expected vs. actual behavior.
- Environment information (OS, Shell, Python version).

### In-Scope Vectors

- Guardrail Bypasses (Region/Role).
- Plugin Evasion.
- Credential Leakage (Logs/Disk/History).
- Namespace Injection.
- Signature Verification Bypass.
