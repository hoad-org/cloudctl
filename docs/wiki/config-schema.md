# config-schema.md

# 🛠️ Configuration Schema

This document defines the **authoritative configuration schema** for `awsctl`. It is a **contract**, not a tutorial. If configuration behavior differs from this document, the implementation is incorrect.

---

## 🏗️ Purpose

`awsctl` configuration is **policy-bearing** and evaluated **before execution**. It defines:
* Visibility of AWS accounts and roles.
* Regional restrictions.
* Safety gates and guardrail triggers.
* Enabled integrations and extensions.

---

## 📐 Configuration Model

Configuration is declarative, static at runtime, and fully validated before use. `awsctl` adheres to a **Strict Parsing** model:
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

---

## ⚙️ Evaluation Order

`awsctl` processes configuration in a strict linear sequence:
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
* **Auto-Discovery:** `awsctl` will never "scan" for accounts or roles.
* **"Best Effort" Parsing:** Partial success is a total failure.

---

## ⚖️ Summary

`awsctl` configuration is **policy**. It is explicit, validated, deterministic, and fail-closed. If the configuration is ambiguous, execution does not proceed.

> [!IMPORTANT]
> This schema is the boundary between user intent and AWS authority. Maintaining its integrity is critical to the **Root of Trust**.
