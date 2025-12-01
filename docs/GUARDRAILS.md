# Guardrails

This document describes the guardrail system used by `awsctl` to enforce safe, consistent, and centralized AWS access boundaries across an engineering organization.

Guardrails are **not** user-configurable.  
They are defined exclusively in the Corporate Registry (`src/awsctl/registry.py`) and enforced at runtime.

---

## 1. Philosophy

Guardrails ensure that all developers operate within the same secure boundaries:

- **Region Locking:** Restrict access to approved AWS regions.
- **Role Prioritization:** Promote least-privilege roles (for example, `ViewOnlyAccess`).
- **Plugin Enforcement:** Mandatory security checks (VPN, device posture, Okta, MFA).
- **Version Enforcement (Roadmap):** Block outdated clients from authenticating.

These policies **cannot be overridden locally**.  
This is validated by the test suite (for example, `test_user_cannot_override_guardrails`).

---

## 2. Source of Truth

All guardrails live in:

    src/awsctl/registry.py

The Registry is a list of dictionaries.  
Each dictionary represents the complete, authoritative policy for a single organization.

Example Registry Definition:

    KNOWN_ORGS = [
        {
            "name": "engineering",
            "label": "Engineering (Main)",
            "start_url": "https://d-123456.awsapps.com/start",
            "default_region": "eu-west-2",

            # --- GUARDRAILS ---
            "allowed_regions": ["eu-west-1", "eu-west-2"],
            "preferred_roles": ["AdministratorAccess", "ViewOnlyAccess"],
            "plugins": ["awsctl.plugins.okta"],
        },
        # ...
    ]

Important:

- Administrators must maintain the exact shape of these dictionaries.
- Changing field names or structure will break hydration.

---

## 3. Hydration Model

User config (`orgs.yaml`):

    enabled_orgs:
      - engineering

Registry entry (`registry.py`):

    {
        "name": "engineering",
        "allowed_regions": ["eu-west-1"],
        # ...
    }

At runtime, `awsctl`:

1. Reads enabled org names from the user file.
2. Loads matching Registry entries.
3. Hydrates the full org definition in memory.
4. Applies guardrails before any AWS action (login, region selection, role selection).

Users cannot override hydrated fields.  
All policy comes from the Registry.

---

## 4. Guardrail Types

### 4.1 Region Restrictions

Definition:

    "allowed_regions": ["eu-west-2"]

Enforcement Points:

- `awsctl login`
- `awsctl switch`
- Interactive region selector
- `--region` flag
- Shell export

Example Violation:

    ERROR: region us-east-1 is not permitted for org 'production'
    exit code: 1

---

### 4.2 Preferred Roles

Definition:

    "preferred_roles": ["ViewOnlyAccess"]

Behavior:

- Preferred roles appear at the top of the interactive selector.
- Reduces human error.
- Encourages least-privilege access.
- Deprecated or unsafe roles naturally fall lower in the list when not listed as preferred.

---

### 4.3 Required Plugins

Definition:

    "plugins": ["awsctl.plugins.okta"]

Behavior:

- Plugins run before login and before region/account selection.
- Enforced plugins cannot be disabled locally.

Typical use cases:

- VPN enforcement.
- MFA validation.
- Okta session checks.
- Device posture / compliance checks.

Example Plugin Failure:

    ✗ VPN connection NOT detected.
    exit code: 1

---

### 4.4 Minimum Client Version (Roadmap)

Definition:

    "min_client_version": "2.0.0"

Purpose:

- Ensure consistent adoption of new guardrails.
- Prevent outdated or noncompliant clients from authenticating.

(Behavior is planned for a future version.)

---

## 5. Ignored Local Overrides

Any attempt by a developer to override guardrails locally is ignored:

    # ~/.awsctl/orgs.yaml
    enabled_orgs:
      - engineering

    # 🚫 This is ignored entirely
    allowed_regions:
      - us-east-1

Verified By:

- `tests/test_config.py::test_user_cannot_override_guardrails`

Registry definitions always prevail.

---

## 6. Lifecycle of a Guardrail Change

1. Admin edits the Registry:

       vim src/awsctl/registry.py

2. Run CI:

       make test

3. Tag release:

       git tag v2.0.1
       git push origin v2.0.1

4. Developers upgrade:

       pipx upgrade awsctl

5. Enforcement begins immediately.  
   Users cannot bypass the new policy.  
   All updated guardrails are applied on the next run.

---

## 7. Admin Checklist

- Update Registry definitions.
- Validate policy via `make test`.
- Update version tag.
- Publish upgrade instructions.
- Verify enforcement in production contexts.

Guardrails, combined with the Registry-backed Hydration Model, ensure that `awsctl` provides consistent, least-privilege, and centrally governed access patterns across the organization.
