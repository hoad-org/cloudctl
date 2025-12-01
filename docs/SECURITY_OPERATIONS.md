# awsctl Security Operations Guide

**Audience:** Security Operations (SecOps), Cloud Security, Compliance  
**Version:** 2.0.0  
**Scope:** Monitoring, auditing, and operational oversight of `awsctl` deployment and usage.

`awsctl` is a workstation security tool that wraps AWS IAM Identity Center (SSO) and enforces centrally-defined guardrails.  
This document provides operational guidance for monitoring security posture, responding to issues, and validating compliance.

---

# 1. Security Model Overview

## 1.1 No Static Credentials

`awsctl` **never** writes AWS access keys to disk. It relies entirely on:

- AWS CLI v2 SSO token cache (`~/.aws/sso/cache/`)
- Ephemeral STS credentials exported into memory only

This architecture:

- Eliminates long-lived keys.
- Reduces credential compromise radius.
- Aligns with AWS best practices for workstation access.

---

## 1.2 Registry-Enforced Guardrails

Security boundaries are centrally defined in:

    src/awsctl/registry.py

Guardrails include:

- Allowed AWS regions.
- Preferred roles.
- Required plugins.
- SSO start URLs.
- Default region.
- (Roadmap) Minimum client version.

**Critical Control:** Local overrides in `~/.awsctl/orgs.yaml` are **ignored**.  
This prevents configuration drift and tampering.

---

## 1.3 Mandatory Pre-Login Plugins

Plugins allow security teams to enforce workstation posture checks such as:

- VPN connectivity.
- Device posture.
- Okta session presence.
- MFA verification.
- IP allowlists.

Plugins defined in the Registry cannot be disabled by users.

Example enforced plugin in Registry:

    "plugins": ["awsctl.plugins.okta"]

If a plugin fails, the login process stops immediately.

---

# 2. Operational Responsibilities

Security Operations teams are responsible for:

- Monitoring enforced plugin results.
- Validating region guardrails.
- Reviewing session anomalies.
- Ensuring user clients are up to date.
- Supporting and verifying correct `awsctl` installation.
- Participating in release governance for Registry changes.

Cloud Platform teams own:

- The Registry definitions (`registry.py`).
- The release process.

---

# 3. Observability and Logging

Although `awsctl` itself is not a logging agent, it interacts with several subsystems that produce logs useful to SecOps.

## 3.1 AWS CloudTrail

All actual AWS actions (CLI or console) generate CloudTrail logs:

- AssumeRole events.
- SSO login flow events.
- STS session issuance.
- Console sign-in events.

Recommendations:

- Monitor role usage against expected patterns.
- Alert on unexpected region usage (should be blocked by guardrail, but alerting adds depth).
- Alert on privileged role usage outside maintenance windows.

---

## 3.2 Plugin Output and System Logs

Plugins print messages to stderr.

Examples:

    ✗ VPN connection NOT detected.
    ✗ Okta session missing — please reauthenticate.

For compliance-sensitive environments:

- Ensure developers know where to view errors.
- Optionally redirect plugin output to local system logs (centralized agents may capture these).

---

## 3.3 AWS SSO Token Lifecycle

AWS CLI stores short-lived SSO tokens in `~/.aws/sso/cache/`.

Tokens:

- Expire after 8–12 hours (typical corporate policy).
- Are automatically refreshed via `awsctl login` / `aws sso login`.
- Pose minimal long-term risk.

SecOps should ensure:

- Token durations align with security policy.
- Compromised endpoints trigger forced SSO logout / account lock.

---

# 4. Incident Response

If suspicious AWS activity is detected:

## 4.1 Immediate Actions

Invalidate the SSO session:

    aws sso logout

Isolate: Remove the workstation from the network if compromise is suspected.

Revoke Access:

- Remove the user from appropriate AWS IAM Identity Center assignments.
- Suspend the user in the corporate IdP (Okta/AzureAD/Google).

Review CloudTrail:

- Look for role escalation, unusual region usage, or STS token chaining.

---

## 4.2 Guardrail-Based Mitigation

If a vulnerability is found in a specific region or role type, you can block it fleet-wide:

Update Registry:

    "allowed_regions": ["eu-west-1"]  # temporarily restrict

Tag a release:

    git tag v2.0.1
    git push origin v2.0.1

Notify developers to upgrade:

    pipx upgrade awsctl

Changes take effect immediately for all upgraded clients.

---

# 5. Compliance and Governance

## 5.1 Policy Enforcement by Design

Because guardrails are:

- Version-controlled.
- Immutable per release.
- Hydrated from the Registry.
- Ignored in local overrides.

`awsctl` is highly auditable and resistant to configuration drift.

This satisfies common compliance controls:

- PCI-DSS 7.x: Least privilege.
- SOC2 CC6.x: Logical access.
- ISO 27001 A.9.x: Access control.

---

## 5.2 Release Governance Workflow

Security teams should be involved in:

- Approving guardrail updates.
- Reviewing new plugins.
- Verifying CI test coverage.
- Validating releases before distribution.

---

# 6. Integration with Corporate Tools

`awsctl` is compatible with:

- MDM / EDR solutions.
- VPN agents.
- Okta Desktop plugins.
- Corporate SSH and proxy configurations.

Recommended integrations:

- Device posture plugin using MDM API.
- VPN enforcement plugin using endpoint or IP range checks.
- Okta plugin for MFA validation.

These can all be enforced centrally through the Registry.

---

# 7. Operational Best Practices

- Require frequent upgrades (monthly recommended).
- Keep Registry definitions small, strict, and versioned.
- Maintain least-privilege roles in `preferred_roles`.
- Use plugins for posture enforcement, not business logic.
- Rotate enforced plugins periodically to catch bypass attempts.
- Audit CloudTrail regularly for anomalies.
- Keep AWS SSO token lifetimes appropriately short.

---

# 8. Summary

`awsctl` significantly strengthens workstation security posture by:

- Eliminating persistent credentials.
- Enforcing centrally-defined region and role guardrails.
- Enforcing corporate security posture via plugins.
- Providing isolation per terminal session.
- Implementing immutable, version-controlled governance.

Verdict: Suitable for enterprise environments requiring high auditability and strong guardrails around privileged access.
