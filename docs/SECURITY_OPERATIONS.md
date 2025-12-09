# file: docs/SECURITY_OPERATIONS.md
# awsctl Security Operations Guide

**System:** `awsctl` Workstation CLI
**Version:** 2.7.0
**Audience:** Security Operations (SOC), Incident Response (IR), Cloud Platform Engineering

---

# 1. Operational Security Model

`awsctl` operates on a **Shared Responsibility Model** for developer workstations:

1.  **The Tool (awsctl):** Guarantees that credentials are ephemeral, in-memory, and bounded by Registry guardrails.
2.  **The Identity Provider (IdP):** (Okta/Entra ID) Handles initial authentication and MFA.
3.  **Security Operations:** Monitors CloudTrail and Endpoint (EDR) logs for anomalies.
4.  **Audit & Compliance:** "Break Glass" access to sensitive roles is locally logged with user justification.

## 1.1 Credential Lifecycle
* **Storage:** Zero static keys on disk.
* **Persistence:** Relies on AWS CLI v2 SSO tokens (`~/.aws/sso/cache/*.json`) which are OIDC artifacts, not AWS keys.
* **Expiration:** Controlled by the AWS Identity Center "Session Duration" setting (typically 8–12 hours).
* **Revocation:** Revoking the user's session in AWS Identity Center **immediately** kills `awsctl` access on the next API call.

## 1.2 The "Context Bridge" Wrapper
SecOps must understand that `awsctl` injects variables into the shell process.
* **Execution Flow:** `User` -> `Shell Function` -> `_awsctl_bin` (Hidden Binary).
* **Process Signature:** The parent process is the shell (`zsh`/`bash`). The child process is `python` executing `awsctl.cli`.
* **Logging:** The payload is sanitized. Standard shell history (`.bash_history`) will show the *command* `awsctl switch`, but **not** the exported credentials.

---

# 2. Observability & Monitoring

Effective monitoring requires correlating **Cloud Telemetry** (AWS) with **Endpoint Telemetry** (EDR).

## 2.1 CloudTrail Fingerprinting
All actions performed via `awsctl` ultimately invoke the AWS CLI or Boto3.

**Critical Note:** `awsctl` does **not** append a custom User-Agent string. Network traffic is indistinguishable from standard AWS CLI usage. You must rely on **Endpoint Telemetry (EDR)** to verify the tool was used.

| Event Name | Source | User Agent Pattern | Meaning |
| :--- | :--- | :--- | :--- |
| `ConsoleLogin` | `signin.amazonaws.com` | `Mozilla/5.0...` | User initiated `awsctl login` (Browser flow). |
| `GetRoleCredentials` | `sso.amazonaws.com` | `aws-cli/2...` | `awsctl` retrieved new STS credentials for a specific account. |
| `AssumeRole` | `sts.amazonaws.com` | `botocore/...` | User is actively using the credentials in their shell. |

## 2.2 Endpoint Detection (EDR) Signatures
To validate `awsctl` usage vs. raw AWS CLI usage (Bypass), monitor process execution on the endpoint.

* **Valid Execution:**
    * Parent: `zsh` or `bash`
    * Child: `python` (or `_awsctl_bin`)
    * CommandLine Contains: `switch`, `login`, `exec`
* **Bypass Indicator:**
    * Direct execution of `aws sso login` without `awsctl` in the process tree immediately prior.

## 2.3 Threat Hunting Queries (SIEM)

### 🕵️ Hunt 1: The "Token Replay" Attack
*Scenario:* An attacker steals the `~/.aws/sso/cache` file and uses it on a different machine.
* **Logic:** Look for an IP Address change within the same SSO Session.
* **Query (CloudWatch Log Insights):**
    ```sql
    fields @timestamp, eventName, sourceIPAddress, userIdentity.principalId
    | sort @timestamp desc
    | filter eventName in ["GetRoleCredentials", "AssumeRole"]
    | stats count_distinct(sourceIPAddress) as ip_count by userIdentity.principalId
    | filter ip_count > 1
    ```

### 🕵️ Hunt 2: Guardrail Evasion (Region Hopping)
*Scenario:* User bypasses `awsctl` to access a restricted region (e.g., `ap-northeast-1` in an `eu-only` org).
* **Logic:** `awsctl` blocks these client-side. Appearance in logs proves a bypass.
* **Query:**
    ```sql
    filter awsRegion not in ["eu-west-1", "eu-west-2", "us-east-1"]
    | filter eventSource = "ec2.amazonaws.com"
    ```

### 🕵️ Hunt 3: Remote Registry Hijack (Tier 3 Only)
*Scenario:* An attacker modifies `~/.awsctl/orgs.yaml` to point to a malicious Registry URL to bypass guardrails.
* **Logic:** Monitor EDR for changes to `orgs.yaml`. If the `registry.url` domain changes from known-good (e.g., `s3.amazonaws.com/my-corp-config`) to unknown, flag it.

## 2.4 Log Formats & Ingestion
* **Audit Log:** `~/.awsctl/audit.log` contains local records of "Break Glass" justifications. Format: `ISO8601 | ORG | ROLE | REASON`.
* **Recommendation:** Ingest `audit.log` into SIEM if highly regulated. Do NOT ingest stdout/stderr.

---

# 3. Incident Response Playbooks

## 3.1 Scenario: Lost/Stolen Laptop
The endpoint is compromised. We must assume the local SSO cache is accessible.

1.  **Immediate Kill (Identity):**
    * Go to **AWS IAM Identity Center** console.
    * Find User -> **Active sessions** -> **Sign out all active sessions**.
    * *Effect:* The cached OIDC token on the laptop becomes invalid immediately.
2.  **IdP Suspension:**
    * Suspend user in Okta/Entra ID.
3.  **Assessment:**
    * There are **no long-term keys** (`AKIA...`) to rotate.
    * Investigate CloudTrail for actions taken *after* the reported loss time.

## 3.2 Scenario: Malicious Insider (Guardrail Bypass)
A developer is suspected of modifying `awsctl` source code to access restricted roles.

1.  **Integrity Check:**
    * Pull `~/.awsctl/orgs.yaml` and `src/awsctl` from the endpoint.
    * Compare the hash of `registry.py` against the official release.
2.  **Audit Check:**
    * Review `~/.awsctl/audit.log` for falsified justifications.
3.  **Containment:**
    * Update the **Remote Registry** (if used) to explicitly deny the user via a new policy rule, or deny access in the IdP.

## 3.3 Scenario: Supply Chain Alert
A vulnerability is discovered in a dependency (e.g., `requests`).

1.  **Triage:** Run `pip-audit` locally to confirm severity.
2.  **Remediation:** Update `pyproject.toml`, bump version, tag, and push.
3.  **Enforcement:** Update the `min_client_version` in the Registry. This will forcibly block all older clients from logging in until they upgrade.

---

# 4. Forensics & Artifacts

If an endpoint is seized for analysis, these are the critical artifacts.

## 4.1 Disk Artifacts

| Path | Purpose | Sensitivity | Action |
| :--- | :--- | :--- | :--- |
| `~/.awsctl/audit.log` | Break Glass Log | **Medium** | Review for justifications on sensitive role access. |
| `~/.awsctl/orgs.yaml` | User Config | Low | Check for unauthorized plugin definitions or Registry URL tampering. |
| `~/.aws/sso/cache/*.json` | Session Tokens | **High** | Contains live OIDC tokens. Revoke immediately. |
| `~/.aws/config` | AWS Profile Config | Low | Check for rogue profiles added manually to bypass the Registry. |
| `~/.bash_history` | Shell History | Medium | Check for `export AWS_...` commands. If found, the user bypassed `awsctl`. |

## 4.2 Memory Forensics
* **STS Credentials:** Short-term keys (`ASIA...`) exist in the environment block of the running shell process (`bash`/`zsh`).
* **Dump Analysis:** A RAM dump of the shell process will reveal these keys.
* **Risk:** Low. These keys expire automatically.

---

# 5. Governance & Change Management

## 5.1 Updating Guardrails
Guardrails are **Code**, not Config.

**Option A: Embedded (Tier 1)**
1.  **Draft:** Create PR updating `src/awsctl/registry.py`.
2.  **Release:** Merge and Tag new version.
3.  **Deploy:** Users upgrade via `pipx`.

**Option B: Remote Registry (Tier 3 - GitOps)**
1.  **Draft:** Update `registry.json` in the config repo.
2.  **Sign:** CI Pipeline signs the JSON with the offline private key (Minisign).
3.  **Publish:** Upload `registry.json` and `registry.json.minisig` to S3.
4.  **Deploy:** Clients pick up changes **immediately** on next run.

## 5.2 Emergency Break-Glass
If `awsctl` is completely broken or compromised:
1.  **Authorization:** CISO / VP Engineering approval required.
2.  **Workaround:** Instruct users to fall back to raw `aws sso login`.
3.  **Impact:** Guardrails (Region Locking, Role Sorting) are **lost** during this window.
4.  **Compensating Control:** SecOps must increase CloudTrail alert sensitivity for "Region Anomaly" detections.

---

# Appendix A: Exit Codes

Automated pipelines can rely on these codes for decision making.

| Code | Meaning | Action |
| :--- | :--- | :--- |
| `0` | Success | Proceed. |
| `1` | Generic Error | Check stderr (Config error, Network fail). |
| `126` | Permission Denied | `exec` failed due to permissions. |
| `127` | Command Not Found | `exec` failed because binary is missing. |
