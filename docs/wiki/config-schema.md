# config-schema.md

# 🛠️ Configuration Schema

This document defines the **authoritative configuration schema** for `cloudctl`. It is a **contract**, not a tutorial. If configuration behavior differs from this document, the implementation is incorrect.

---

## 🏗️ Purpose

`cloudctl` configuration is **policy-bearing** and evaluated **before execution**. It defines:
* Visibility of AWS accounts and roles.
* Regional restrictions.
* Safety gates and guardrail triggers.
* Enabled integrations and extensions.

---

## 📐 Configuration Model

Configuration is declarative, static at runtime, and fully validated before use. `cloudctl` adheres to a **Strict Parsing** model:
* **No Permissive Mode:** Unknown keys, type mismatches, or partial configs trigger a hard failure.
* **Deterministic:** Authority flows from configuration to execution; the reverse is never permitted.



---

## 📑 Schema Definition

### 1. `version` (Required)
Declares the schema version as an integer.
* **Failure:** Missing or unsupported versions result in an immediate abort.

### 2. `organization` (Required)
Defines the logical AWS organization context.
* **Fields:** `name` (string).
* **Semantics:** Used for identity scoping and audit evidence. Must be stable.

### 3. `accounts` (Required)
An explicit list of allowed AWS accounts.
* **ID:** Must be a 12-digit string.
* **Constraints:** Duplicate IDs are rejected. No implicit account discovery.
* **Failure:** Invalid IDs or empty lists result in an abort.



### 4. `roles` (Required)
Defines assumable IAM roles.
* **Fields:** `name` (string), `sensitive` (boolean).
* **Semantics:** `sensitive: true` triggers mandatory UX confirmation.
* **Failure:** Roles not listed are invisible to the client.

### 5. `regions` (Optional)
Defines a regional allowlist.
* **Semantics:** Limits where credentials may be used. Absence implies no regional restriction.

### 6. `guardrails` (Optional)
Additional safety constraints.
* **Semantics:** Enforces UX safety (e.g., `require_confirmation_for`). Guardrails never provide auto-approval.

### 7. `plugins` (Optional)
Configures optional extensions.
* **Constraints:** Plugins are untrusted and cannot override policy. Plugin initialization failure triggers a hard abort.

### 8. `provider` (Optional — Org-level)

Selects the cloud backend for an individual org entry. Defaults to `"aws"` for backward compatibility with existing configurations.

| Value | Backend | Required CLI |
|-------|---------|--------------|
| `aws` | AWS IAM Identity Center (SSO) | AWS CLI v2 |
| `azure` | Microsoft Azure RBAC | Azure CLI (`az`) |
| `gcp` | Google Cloud IAM | gcloud SDK |

**Example multi-cloud `orgs.yaml`:**
```yaml
orgs:
  - name: engineering
    provider: aws          # optional; default
    sso_start_url: https://d-xxxxxxxxxx.awsapps.com/start
    sso_region: us-east-1
    default_region: us-east-1
    allowed_regions: [us-east-1, us-west-2]

  - name: azure-prod
    provider: azure
    tenant_id: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    default_subscription: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    roles: [Contributor, Reader]

  - name: gcp-prod
    provider: gcp
    default_project: my-project-id
    roles: [roles/viewer, roles/editor]
```

**Emitted environment variables by provider:**

| Provider | Variables |
|----------|-----------|
| `aws` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` |
| `azure` | `AZURE_SUBSCRIPTION_ID`, `AZURE_TENANT_ID`, `ARM_SUBSCRIPTION_ID`, `ARM_TENANT_ID`, `ARM_ACCESS_TOKEN` |
| `gcp` | `GOOGLE_CLOUD_PROJECT`, `CLOUDSDK_CORE_PROJECT`, `GCLOUD_PROJECT`, `GOOGLE_OAUTH_ACCESS_TOKEN` |

---

## ⚙️ Evaluation Order

`cloudctl` processes configuration in a strict linear sequence:
1. **Schema Validation:** Structural integrity and type checks.
2. **Semantic Validation:** Logic checks (e.g., duplicate IDs, valid region strings).
3. **Registry Construction:** Building the internal policy source of truth.
4. **Execution Eligibility:** Final check before the CLI accepts user input.

**Failure at any stage halts execution.**



---

## 🚫 Forbidden Patterns

To preserve the security model, the following are strictly prohibited:
* **Implicit Defaults:** Every setting must be explicitly declared.
* **Environment-Variable Overrides:** Core policy cannot be changed via the environment.
* **Auto-Discovery:** `cloudctl` will never "scan" for accounts or roles.
* **"Best Effort" Parsing:** Partial success is a total failure.

---

## ⚖️ Summary

`cloudctl` configuration is **policy**. It is explicit, validated, deterministic, and fail-closed. If the configuration is ambiguous, execution does not proceed.

> [!IMPORTANT]
> This schema is the boundary between user intent and AWS authority. Maintaining its integrity is critical to the **Root of Trust**.
