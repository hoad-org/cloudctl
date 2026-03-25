# 🧭 Tenant Bootstrap – Operator Runbook

This runbook describes how to safely execute and reason about the **Tenant Bootstrap**. It is intended for platform operators and on-call engineers, not for general onboarding.

This repository initializes and reconciles **organization-level control-plane identity and trust primitives**. It is safe to re-run and does **not** manage application workloads.

---

## 🎯 Purpose & Scope

The Tenant Bootstrap establishes and maintains the **Root of Trust** for an AWS Organization.

### Responsibilities
- **Identity & Trust:** Organization-wide OIDC and IAM roles.
- **Terraform Foundation:** Backend infrastructure (S3, DynamoDB, KMS).
- **Guardrails:** Permission boundaries and security baselines.
- **GitHub Federation:** Trust establishment and secret distribution.
- **Auditability:** Control-plane evidence and logging.

### Out of Scope
- Account Vending (AVM).
- Workload deployment or networking bootstrap.
- Continuous orchestration.

---

## 📋 Execution Requirements

The operator must be authenticated to both AWS and GitHub before execution.

### AWS Requirements
The caller must be authenticated via AWS SSO, assumed role, or environment credentials with permissions for:
* **IAM:** Roles, permission boundaries, and OIDC providers.
* **Storage/State:** S3 and DynamoDB (Terraform backends).
* **Encryption:** KMS (control-plane keys).
* **Orchestration:** CloudFormation StackSets.

### GitHub Requirements
* **CLI:** The GitHub CLI (`gh`) must be installed and authenticated.
* **Permissions:** Admin access to any repositories listed in `trusted_repos` for environment and secret management.

---

## 🚀 How to Run

Execution is synchronous, single-shot, and designed to be run from a local terminal or a CI runner.

```bash
# Setup dependencies
poetry install

# Execute bootstrap for a specific environment
poetry run python src/main.py configs/<environment>.yaml
```

**Example:**
```bash
poetry run python src/main.py configs/bt-dev.yaml
```

---

## 🔄 Reconciliation Model

This tool is a **reconciler**, not a one-time installer. It follows these key principles:
* **Source of Truth:** YAML configuration defines the desired state.
* **Reuse:** Existing resources are reused whenever possible.
* **Safety:** Re-running the bootstrap is safe and expected.
* **Self-Healing:** Drift is corrected automatically upon execution.

### GitHub-Specific Behavior
For each repository listed in `trusted_repos`:
1.  **Environment Creation:** Target environments (e.g., `bt-dev`) are created if missing.
2.  **Secret Sync:** Secrets are intentionally overwritten to match the declared state.
3.  **Isolation:** Repositories **not** listed in the configuration are never modified.

---

## 🚦 Interpreting Output

The bootstrap emits structured logs to guide the operator:

| Signal | Meaning |
| :--- | :--- |
| **✅ Verified existing …** | Resource is compliant; no action taken. |
| **🔑 Setting secret …** | Idempotent secret reconciliation (normal behavior). |
| **⚠️ Warning** | Informational or transitional state. |
| **❌ Error** | Actionable failure requiring operator review. |

> [!NOTE]
> Warnings do not indicate partial execution unless followed by an error.

---

## 🛡️ Rollback & Recovery

There is no destructive "undo" command. To rollback, utilize the Git-centric workflow:
1.  **Revert:** Revert the YAML configuration in Git to a known-good state.
2.  **Re-run:** Execute the bootstrap again to reconcile the environment to the reverted state.

**The bootstrap does not delete:** AWS accounts, IAM roles, GitHub repositories, or Terraform state. All changes are additive or reconciling.

---

## 🚫 Explicit Non-Goals

This repository will **not**:
* Vend AWS accounts or manage VPCs.
* Deploy application-level infrastructure.
* Enforce SCP/RCP business logic.
* Run continuously as a resident controller.

---

## ⚖️ Operational Guidance

* **Treat as Infrastructure:** Consider this repository as critical control-plane code.
* **Small Changes:** Prefer small, deliberate configuration updates over large bulk changes.
* **Trust the Reconciler:** Re-run the tool rather than manually fixing drift in the AWS Console.
* **The 10-Year Rule:** If a change cannot be safely applied to a 10-year-old AWS Organization, it likely does not belong here.

> [!IMPORTANT]
> The Tenant Bootstrap is designed to be **safe, deterministic, and boring.** If execution results are surprising, revisit the configuration or scope immediately.
