# Administrator Guide

This guide describes how platform, security, and cloud foundation teams manage and control `awsctl` across an engineering organization.  
`awsctl` follows a **Registry-backed Hydration Model**.  
This means the authoritative definitions of organizations, URLs, regions, and guardrails live centrally in `src/awsctl/registry.py`.  
End-users only select *which* orgs are enabled; all other configuration is enforced by the Registry.

---

## 1. Architecture Overview

At runtime, `awsctl` loads configuration from two sources:

---

### 1. User Enablement File (`~/.awsctl/orgs.yaml`)

**Scope:** User preference  
**Content:** Only lists which orgs are enabled (plus optional plugin configuration).

Example:

    enabled_orgs:
      - engineering
      - production

    plugins:
      enabled:
        - awsctl.plugins.okta

Users do **not** specify:

- `start_url`
- `sso_region`
- `default_region`
- `allowed_regions`
- `preferred_roles`
- `min_client_version`

All such fields are centrally defined and enforced via the Registry.

---

### 2. Corporate Registry (`src/awsctl/registry.py`)

**Scope:** Immutable policy (compiled into the tool)  
**Content:** Full authoritative configuration and guardrails for each org.

At runtime, `awsctl`:

- Hydrates all details from the Registry.
- Builds in-memory org objects.
- Applies guardrails from Registry definitions.
- Ignores user-defined overrides.

This behavior is validated by the test suite (for example, `test_user_cannot_override_guardrails`).

---

## 2. Administrator Responsibilities

Administrators own:

- Registry definitions.
- Release management of the `awsctl` binary.
- Region guardrails.
- Preferred role ordering.
- Plugin policy (VPN checks, Okta checks, MFA validation, etc.).
- Governance of organization identity boundaries.
- Upstream testing and CI.

Developers own:

- Selecting which orgs they want to use.
- Running `awsctl setup`.
- Using `awsctl switch` to assume roles.
- Upgrading when instructed.

---

## 3. The Registry (`src/awsctl/registry.py`)

This file is the canonical source of truth.

- It is a Python **list of dictionaries**, not a mapping.
- The hydration logic iterates over the list, matching on `"name"`.

### 3.1 Example Registry Entry (Correct Structure)

    # src/awsctl/registry.py

    KNOWN_ORGS = [
        {
            "name": "engineering",
            "label": "Engineering (Main)",
            "start_url": "https://d-123456.awsapps.com/start",
            "sso_region": "eu-west-1",
            "default_region": "eu-west-2",

            # 🛡️ GUARDRAILS — centrally enforced
            "allowed_regions": ["eu-west-1", "eu-west-2"],
            "preferred_roles": ["AdministratorAccess", "ViewOnlyAccess"],

            # Enforced plugins (always run)
            "plugins": ["awsctl.plugins.okta"],
        },
        {
            "name": "production",
            "label": "Production (Restricted)",
            "start_url": "https://d-987654.awsapps.com/start",
            "sso_region": "eu-west-1",
            "default_region": "eu-west-1",

            # 🛡️ Strict guardrails
            "allowed_regions": ["eu-west-1"],
            "preferred_roles": ["ReadOnlyAccess"],

            "plugins": [],
        },
    ]

### 3.2 Rules

- Users cannot modify this file.
- Changing values requires rebuilding and releasing a new `awsctl` version.
- Guardrails apply immediately when users upgrade.
- All local overrides are ignored.
- Field names must match exactly or hydration will fail.

---

## 4. Release Workflow (Administrators Only)

Because the Registry is embedded in the binary, updates require a release.

### 4.1 Update Steps

1. Modify Registry:

       vim src/awsctl/registry.py

2. Run full CI suite:

       make test

3. Commit:

       git commit -m "chore(registry): update prod guardrails"

4. Tag release:

       git tag -a v2.0.1 -m "Release v2.0.1"
       git push origin v2.0.1

5. CI (for example, GitHub Actions) builds the new wheel and release artifacts.

### 4.2 Developer Upgrade

Developers upgrade using:

    pipx upgrade awsctl

Upgrades immediately apply the new guardrails for all users.

---

## 5. Policy and Guardrail Types

### 5.1 Region Restrictions

Definition (Registry):

    "allowed_regions": ["eu-west-2"]

When enforced in:

- Login (`awsctl login`).
- Context switching (`awsctl switch`).
- `--region` flag usage.
- Interactive TUI selection.

Example violation:

    ERROR: region us-east-1 is not permitted for org 'production'
    exit code: 1

---

### 5.2 Role Ordering (Preferred Roles)

Definition:

    "preferred_roles": ["ViewOnlyAccess", "Auditor"]

Behavior:

- Preferred roles appear at the top of the interactive role selector.
- Useful for reducing human error and promoting least privilege.
- Deprecated roles can be pushed downward by simply not listing them.

---

### 5.3 Plugin Enforcement

Definition:

    "plugins": ["awsctl.plugins.okta"]

Behavior:

- Plugins run before login.
- Enforced plugins cannot be disabled locally.

Common uses:

- VPN compliance.
- Okta or MFA validation.
- Internal network checks.
- Security posture verification.

For plugin implementation details, see `docs/PLUGIN_DEVELOPMENT.md`.

---

## 6. Enterprise Deployment

### 6.1 Controlled Distribution (Recommended)

Use version pinning via Git tags:

    pipx install "git+ssh://git@github.com/your-org/awsctl.git@v2.0.0"

Advantages:

- Reproducible deployments.
- Auditable source control.
- Prevents drift.
- Registry changes are tied to a release.
- CI integration.

---

### 6.2 Version Enforcement (Planned Feature)

Define a minimum allowed client version:

    "min_client_version": "2.0.0"

Planned behavior:

- If a user runs an older version, the tool refuses authentication until upgraded.

---

## 7. Governance Summary

| Scope                 | Location                     | Owned By  | Modifiable?                              |
|-----------------------|------------------------------|-----------|-------------------------------------------|
| Policies and Guardrails | `src/awsctl/registry.py`   | Admins    | No (requires code change + release)       |
| User Selection        | `~/.awsctl/orgs.yaml`        | Developers| Yes (non-security fields only)           |
| Credentials           | Shell environment (ephemeral)| System    | No (never written to disk by `awsctl`)    |

---

## 8. Administrator Checklist

**Before Release:**

- Update Registry definitions.
- Validate guardrails (`make test`).
- Confirm plugin correctness.
- Run full linting and tests.
- Tag and push release.
- Communicate upgrade instructions to developers.

**After Release:**

- Monitor adoption.
- Validate that guardrail changes propagated.
- Support teams with migration issues.

---

## 9. Summary

Administrators use the Registry model to centrally control:

- Regions.
- Roles.
- URLs.
- SSO boundaries.
- Plugin enforcement.

Users cannot override or bypass these definitions.  
The Registry ensures compliance, consistency, and operational safety across the entire engineering organization.
