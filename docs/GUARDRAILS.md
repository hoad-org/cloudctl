# file: docs/GUARDRAILS.md
# Guardrails & Governance Model — awsctl v2.8.0

## 1. Overview

Guardrails allow corporate governance teams to centrally enforce boundaries.
Local user configuration (`orgs.yaml`) **cannot** override these settings.

## 2. Region Guardrails

Defined in Registry: `allowed_regions`.

> allowed_regions:
>   - us-east-1
>   - us-east-2

- **Enforcement:** Attempting to login/switch to `eu-west-1` results in **Immediate Termination**.
- **Default:** Empty list implies **Deny All**.

## 3. Role Guardrails

### Preferred Roles

Roles in `preferred_roles` are sorted to the top of the selection list to encourage least-privilege access.

### Sensitive Roles (Break Glass)

Roles in `sensitive_roles` require mandatory justification.

## 4. Minimum Client Version

> min_client_version: "2.8.0"

- **Behavior:** If the running client is older than this value, Login is blocked with an upgrade instruction.

## 5. Plugin Namespace Guardrails

To prevent Arbitrary Code Execution (ACE) via config tampering:

- Plugins **MUST** reside in `awsctl.plugins.*`.
- Loading `os` or `subprocess` directly via the plugin loader is blocked.
