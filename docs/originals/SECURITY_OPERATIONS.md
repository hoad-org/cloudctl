# file: docs/SECURITY_OPERATIONS.md
# cloudctl Security Operations Manual (v2.8.1)

**Audience:** Cloud Security, SecOps, and Compliance Teams.

---

## 1. Overview

cloudctl enforces enterprise access controls and provides audit mechanisms for AWS identity workflows.
It operates on a **Shared Responsibility Model**:

- **Tool:** Enforces ephemeral credentials and guardrails.
- **SecOps:** Monitors logs and maintains the Registry.

## 2. Registry Management

### Manual Configuration (Pilot Phase)

During the pilot, `cloudctl` guardrails and settings are defined locally in `~/.cloudctl/orgs.yaml`.

- **Source of Truth:** Internal Confluence Documentation.
- **Integrity:** Relies on users correctly copying the approved configuration.
- **Updates:** Users must manually update their local file when SecOps publishes new guardrails.

### Remote Signed Registry (Tier 3 - Future State)

The target architecture allows dynamic policy updates without client upgrades.

- **Pipeline:** JSON is signed offline using Minisign.
- **Verification:** Client enforces a **Pinned Trust Anchor** (Public Key hardcoded in binary).
- **Fail-Closed:**
    - Signature Mismatch → **EXIT(1)**
    - File too large (>1MB) → **EXIT(1)** (DoS Protection)
    - Non-HTTPS URL → **EXIT(1)** (SSRF Protection)

## 3. Break Glass Procedures

Accessing a role tagged as `sensitive_roles` triggers:

1.  **Interactive Prompt:** User must provide a text justification.
2.  **Local Audit:** Logged to `~/.cloudctl/audit.log`.
    - *Format:* `ISO8601 | ORG | ROLE | REASON`

**Emergency Procedure:**

If `cloudctl` fails, SecOps must authorize users to fallback to raw `aws sso login`.

- *Risk:* Guardrails (Region locking) are lost during fallback.
- *Mitigation:* Increase CloudTrail alerting for `us-east-1` (or other non-sovereign regions).

## 4. Monitoring & Alerts

Correlate **Endpoint Telemetry** with **CloudTrail**.

- **Valid Pattern:** Process `python` (child of `bash`) calls `aws sso get-role-credentials`.
- **Bypass Pattern:** Direct execution of `aws` without `cloudctl` parent.

## 5. Exit Codes

| Code | Meaning | Action |
| :--- | :--- | :--- |
| **0** | Success | Normal operation. |
| **1** | Generic Error | Check stderr (Config/Network). |
| **126** | Permission Denied | Wrapper failed to execute binary. |
| **127** | Command Not Found | `_cloudctl_bin` missing from PATH. |
| **130** | Interrupted | User Ctrl+C during prompt. |
