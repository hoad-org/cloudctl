# security-operations.md

# 🛡️ Security Operations

This document defines the **operational procedures** for managing, auditing, and responding to incidents within the `cloudctl` ecosystem. It outlines how to maintain the security posture defined in the [Security Overview](./security-overview.md) during day-to-day use.

---

## 🧾 Audit and Observability

`cloudctl` operations are designed to be transparent and verifiable through native cloud logging.

### 1. AWS CloudTrail Attribution
Every successful context switch results in an `AssumeRole` event in CloudTrail.
* **Identity Mapping:** The `sourceIdentity` or `RoleSessionName` in CloudTrail is mapped back to the unique Identity Provider (IdP) actor.
* **Automation:** Security teams should monitor for `AssumeRole` events where the `userAgent` matches `cloudctl/*`.



### 2. Local Forensic Artifacts
While `cloudctl` does not persist credentials, it does maintain a minimal, non-sensitive execution log for troubleshooting:
* **Location:** `~/.config/cloudctl/logs/` (or OS equivalent).
* **Content:** Command history, registry sync timestamps, and plugin execution results.
* **Security:** Logs **never** contain session tokens, secrets, or PII.

---

## 🗂️ Registry Management

The **Policy Registry** is the operational control point for `cloudctl` behavior.

### 1. Registry Updates
Registries should be managed via a **GitOps workflow**:
* **Validation:** All registry changes must pass schema validation via CI.
* **Review:** Changes to `allowed_roles` or `sensitive_accounts` require approval from the Security or Platform team.

### 2. Emergency Revocation
To immediately block a specific role or account from being accessed via `cloudctl`:
1. Update the central registry to move the target to a `deny_list`.
2. Push the update.
3. `cloudctl` clients will enforce the block upon their next registry sync (typically every 60 minutes or on force-refresh).

---

## 🚨 Incident Response

In the event of a suspected workstation compromise or credential exfiltration:

### 1. Session Invalidation
Since `cloudctl` uses STS temporary credentials, access can be revoked globally via AWS:
* **Action:** Apply an inline IAM policy to the compromised role to deny all actions for sessions issued before the incident timestamp (`aws:TokenIssueTime`).



### 2. Identity Provider Suspension
If a user's local machine is compromised:
* **Action:** Suspend the user's account in the Identity Provider (e.g., Okta, Entra ID).
* **Effect:** `cloudctl` will fail to refresh or broker new credentials immediately.

---

## 🔄 Vulnerability Management

### 1. Version Enforcement
The registry can enforce a `min_version` for the `cloudctl` binary. 
* **Action:** If a security vulnerability is found in an older version of `cloudctl`, update the `min_version` in the registry.
* **Effect:** All older clients will refuse to execute until the user updates.

### 2. Secret Scanning
`cloudctl` developers and operators must ensure that:
* **Config files** do not contain hardcoded keys.
* **CI/CD pipelines** use `git-secrets` or `trufflehog` to prevent credential leakage in the registry repo.

---

## ✅ Operational Checklist

| Task | Frequency | Responsibility |
| :--- | :--- | :--- |
| **Registry Schema Check** | Per PR | Platform Team |
| **CloudTrail Audit Review** | Weekly | Security Team |
| **IdP Integration Health** | Monthly | IT Operations |
| **Version Deprecation** | As Needed | Security Team |

---

## ⚖️ Summary

Security Operations for `cloudctl` focus on **centralized policy** and **decentralized execution**. By leveraging native AWS and IdP controls, operators can manage human access at scale without managing local state.

> [!TIP]
> Always prefer automated revocation via IAM policies over manual workstation intervention during an incident.