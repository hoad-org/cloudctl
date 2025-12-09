# file: docs/GUARDRAILS.md
# Guardrails

This document describes the guardrail system used by **awsctl** (v2.7.0+).
Guardrails are **not** user-configurable. They are defined exclusively in the Corporate Registry (Embedded or Remote).

---

## 1. Philosophy

Guardrails ensure that all developers operate within the same secure boundaries:

- **Region Locking:** Restrict access to approved AWS regions.
- **Role Prioritization:** Promote least-privilege roles.
- **Plugin Enforcement:** Mandatory security checks (VPN, device posture).
- **Namespace Isolation:** Prevent execution of untrusted code.
- **Audit & Compliance:** Enforce justification for high-privilege access.

---

## 2. Hydration Model

User config (`orgs.yaml`) only enables an org and optionally configures the Remote Registry URL.
The Registry acts as the immutable policy source.

At runtime, `awsctl`:

1.  Reads enabled org names.
2.  Hydrates the full definition from the Registry (Embedded `registry.py` or Signed Remote JSON).
3.  Applies guardrails before any AWS action.

**Local overrides are ignored.**

---

## 3. Guardrail Types

### 3.1 Region Restrictions

Definition:

    "allowed_regions": ["eu-west-2"]

Enforced during `login`, `switch`, and `exec`. Violations return `exit code: 1` immediately.

### 3.2 Required Plugins

Definition:

    "plugins": ["awsctl.plugins.okta"]

Plugins run before login. If they fail (exit code != 0), the process aborts.

### 3.3 Role Prioritization (Least Privilege)
Definition:

    "preferred_roles": ["ViewOnlyAccess"]

Behavior:
Promotes least-privilege roles to the top of the interactive selector, making it the default choice and encouraging developers to choose the lowest necessary access level.

### 3.4 Namespace Isolation (ACE Prevention)
Definition:

    "plugins": ["awsctl.plugins.internal_check"]

Enforcement:
Blocks dynamically loaded plugins that do not adhere to approved internal namespaces (e.g., `awsctl.plugins.*` or `myorg.plugins.*`). This prevents **Arbitrary Code Execution (ACE)** via config file tampering.

### 3.5 TTY Guard (Operational Safety)

The binary detects if it is running in an interactive terminal during an export operation.
If detected, it refuses to print credentials to the screen to prevent accidental exposure.

### 3.6 Break Glass Audit (New in v2.5)

Definition:

    "sensitive_roles": ["AdministratorAccess"]

Enforcement:
If a user selects a role flagged as sensitive, `awsctl` pauses execution. The user must explicitly provide a text justification (e.g., "JIRA-1234"). This justification is logged locally to `~/.awsctl/audit.log` for compliance auditing.

### 3.7 Minimum Version Enforcement (New in v2.5)

Definition:

    "min_client_version": "2.5.0"

Enforcement:
During login or context switching, the client checks its own version against the Registry requirement. If the client is too old, it aborts with a message instructing the user to upgrade (e.g., `pipx upgrade awsctl`).

---

### 4. Evolution of Controls

* **v2.2:** Added Role Prioritization and Namespace Isolation.
* **v2.5:** Added Break Glass Audit and Minimum Version Enforcement to support Enterprise Governance.

---

## 5. Potential Future Guardrails (Supported by Current Architecture)

The Registry-backed architecture is flexible enough to implement contextual guardrails by simply defining new fields in `src/awsctl/registry.py` and writing corresponding code validation.

| Team/Scenario | Potential Guardrail | Definition / Enforcement Mechanism |
| :--- | :--- | :--- |
| **Data Security** | **Service Allow/Deny List** | Define a field listing `allowed_services: ["s3", "ec2"]`. Enforcement requires intercepting the `aws exec` command to check the first argument against the list. |
| **Audit/Compliance** | **Remote Audit Hook** | Define `audit_webhook: "https://..."`. Instead of local logging, Break Glass justifications are sent to a SIEM/Slack via HTTPS. |
| **Security Operations** | **Role Deny List (Exceptions)** | Define a field `denied_roles_in_account: ["BreachResponder"]`. Used to block specific high-privilege roles in specific accounts even if they exist in the AWS API. |
| **FinOps** | **Mandatory Region Tagging** | Define `enforce_tags: ["CostCenter"]`. The tool could check IAM policy tags for compliance upon assumption. |
