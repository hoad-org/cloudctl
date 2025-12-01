# awsctl Security Appraisal

**Version:** 2.0.0  
**Audience:** Information Security, Cloud Security, Risk and Compliance  
**Scope:** Desktop / Developer Workstation AWS Access Controls

This document provides a formal appraisal of the security posture of `awsctl`, focusing on credential handling, guardrail enforcement, access boundaries, and operational risk.

---

# 1. Executive Summary

`awsctl` is a developer productivity tool that wraps AWS IAM Identity Center (SSO) with strong workstation guardrails.  
It **does not** manage long-term credentials and **does not** write AWS keys to disk.

The tool introduces:

- **Registry-backed guardrails** that prevent region drift and enforce least-privilege role selection.
- **Mandatory plugin hooks** for corporate VPN, device posture, or Okta checks.
- **Secure in-memory credentials** via shell export (Print and Evaluate).
- **Immutable policy control** through versioned releases of the central Registry.

**Security Verdict:**

- ✔ Low Risk  
- ✔ High Security Value  
- ✔ Strong Policy Enforcement without friction

---

# 2. Architecture and Data Flow

The `awsctl` architecture consists of three key components.

## 2.1 User Config (`~/.awsctl/orgs.yaml`)

Contains only:

    enabled_orgs:
      - engineering

    plugins:
      enabled:
        - awsctl.plugins.okta

It cannot override:

- SSO URLs
- SSO regions
- Allowed AWS regions
- Preferred roles
- Mandatory plugins

Local override attempts are ignored (validated by `test_user_cannot_override_guardrails`).

---

## 2.2 Corporate Registry (`src/awsctl/registry.py`)

The Registry is a list of dictionaries, each representing an organization definition.  
This is compiled into the binary.

Example:

    KNOWN_ORGS = [
        {
            "name": "engineering",
            "start_url": "https://d-123456.awsapps.com/start",
            "default_region": "eu-west-2",

            # --- Guardrails ---
            "allowed_regions": ["eu-west-1", "eu-west-2"],
            "preferred_roles": ["AdministratorAccess", "ViewOnlyAccess"],
            "plugins": ["awsctl.plugins.okta"],
        },
    ]

Administrators update it via versioned releases.  
The Registry is the sole source of security boundaries.

---

## 2.3 Credential Flow

`awsctl` does not generate AWS credentials.  
It delegates all credential management to the official AWS CLI v2 SSO token store:

- SSO token is stored under `~/.aws/sso/cache/` (JSON files).
- STS credentials are acquired just-in-time and exported into memory only.
- Credentials are never persisted to `~/.aws/credentials`.
- No long-lived keys are created.

This model minimizes the credential footprint on developer machines.

---

# 3. Threat Model

## 3.1 Assets Protected

- AWS console/session access.
- Elevated/developer IAM roles.
- Sensitive AWS environments (prod, PCI, restricted regions).
- Corporate network and Okta identity posture.

## 3.2 Trust Boundaries

- User workstation → `awsctl`: CLI local execution.
- `awsctl` → AWS CLI: Delegation boundary.
- `awsctl` → AWS SSO: Uses browser-based login.
- `awsctl` → Registry: Immutable policy, code-level enforcement.

## 3.3 Attacker Classes Considered

- Malicious insider developer.
- Compromised developer workstation.
- Unapproved scripts or automation.
- Token/session replay attacks.
- Region drift attempts.
- Plugin bypass attempts.

---

# 4. Security Controls

## 4.1 Region Guardrails (Strong)

Registry-defined allowed regions:

    "allowed_regions": ["eu-west-2"]

Enforced during:

- Login.
- Context switching (`awsctl switch`).
- Interactive menus.
- Non-interactive flag use (`--region`).
- Shell export.

Violation returns:

    ERROR: region us-east-1 is not permitted for org 'production'

Risk Reduction: Prevents environment sprawl, blast-radius errors, and regulatory drift.

---

## 4.2 Role Guardrails (Medium-Strong)

Registry defines:

    "preferred_roles": ["ViewOnlyAccess"]

Preferred roles appear first in the selector.

Risk Reduction: Encourages least-privilege selection and reduces accidents.

---

## 4.3 Mandatory Plugins (Strong)

Plugins provide pre-login enforcement:

- VPN checks.
- Device posture.
- Okta/MFA assurance.
- IP allowlists.

If a plugin fails:

    ✗ VPN connection NOT detected.
    exit code: 1

The user cannot proceed.

Risk Reduction: Ensures environment posture before AWS access.

---

## 4.4 Hydration Model (Very Strong)

Local config is deliberately minimal. Users cannot override any policy:

- Registry → Tool (immutable).
- Local YAML → Enablement only.
- Overrides ignored (tested).

Risk Reduction: Eliminates config drift and local tampering.

---

## 4.5 No Static Keys Ever (Very Strong)

- No long-lived keys generated.
- No writes to `~/.aws/credentials`.
- Only AWS CLI SSO token cache is used.
- Credentials remain in-memory only.

Risk Reduction: Prevents leaked keys and reduces credential lifetime window.

---

## 4.6 Shell Export Security

`awsctl` injects credentials via the Trojan Horse wrapper, effectively:

    eval "$(_awsctl_bin ...)"

Properties:

- Credentials do not hit disk.
- Each terminal tab has isolated credentials.
- Exports follow OS process boundaries.
- Compatible with ephemeral session workflows.

Risk Reduction: Limits credential exposure to the current shell session.

---

# 5. Residual Risks

Although `awsctl` greatly improves AWS SSO workstation hygiene:

- A fully compromised laptop can still misuse exported credentials.
- SSO token lifetime is determined by AWS / IdP policy, not `awsctl`.
- Plugins must be correctly implemented to avoid false negatives.
- Misconfigured Registry entries propagate via releases.

These risks are inherent to AWS SSO workflows and are not introduced by the tool.

---

# 6. Security Recommendations

For maximum safety:

- Enforce corporate VPN checks through plugins.
- Require MFA via Okta or IdP integrations.
- Minimize allowed regions to operational necessities.
- Limit `preferred_roles` to least-privilege roles.
- Use frequent release cycles for Registry updates.
- Use CI (pytest) to validate guardrails before shipping releases.
- Prefer short AWS SSO token lifetimes where possible.

---

# 7. Governance and Auditability

Because guardrails are defined in a central file (`registry.py`) and version-controlled:

- All changes are auditable.
- Policy changes require a release tag.
- No silent drift is possible.
- Developers cannot bypass guardrails.

This yields high audit confidence for regulated workloads.

---

# 8. Overall Security Posture

`awsctl` significantly enhances AWS workstation security by:

- Removing static tokens entirely.
- Centralizing access boundaries.
- Enforcing least privilege.
- Ensuring corporate compliance posture.
- Providing predictable, governed guardrails.

**Final Verdict:**

- ✔ Suitable for enterprise use  
- ✔ Strong guardrail enforcement  
- ✔ No credential persistence  
- ✔ Minimal attack surface  
- ✔ High compliance value
