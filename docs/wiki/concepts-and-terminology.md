# concepts-and-terminology

# Concepts and Terminology

This document defines the **authoritative vocabulary** used by awsctl.

All other documentation, code, reviews, and discussions are expected to use
these terms consistently.

If a term is ambiguous here, it is ambiguous everywhere.
This document exists to prevent that.

---

## Why This Document Exists

awsctl operates at the intersection of:

- Human identity
- Organizational policy
- AWS IAM
- Client-side execution
- Security controls

Many commonly used terms are overloaded or misused in this space.
Misunderstanding terminology leads directly to security errors.

This document resolves those ambiguities.

---

## Core Concepts

### awsctl

**Definition:**  
A client-side identity broker and execution control tool for AWS.

**Not:**
- An authentication system
- A credential store
- An IAM replacement
- An automation engine

awsctl mediates *intent* between humans and AWS.

---

### Identity Provider (IdP)

**Definition:**  
The external system that authenticates a human user  
(e.g. AWS IAM Identity Center, Okta, Azure AD).

**Key Properties:**
- awsctl does not authenticate users
- awsctl trusts IdP assertions
- IdP is authoritative for identity

---

### Authentication

**Definition:**  
The act of proving who a user is.

**Important:**  
Authentication does **not** imply authorization.

awsctl never performs authentication.

---

### Authorization

**Definition:**  
The act of determining what a user is allowed to do.

In awsctl, authorization is enforced by:
- Configuration
- Registry policy
- AWS IAM
- Guardrails

Authorization failures are explicit and terminal.

---

### Identity Assertion

**Definition:**  
A short-lived proof of authenticated identity issued by the IdP
and consumed by AWS STS.

awsctl does not generate assertions.
It only brokers their use.

---

### AWS STS (Security Token Service)

**Definition:**  
AWS service that issues short-lived credentials based on trust policies.

awsctl uses STS to:
- Assume roles
- Obtain temporary credentials

STS is the final authority for access.

---

## Configuration & Policy Concepts

### Configuration

**Definition:**  
A static, declarative policy document that defines:
- Allowed accounts
- Allowed roles
- Regions
- Guardrails
- Plugins

Configuration is evaluated **before execution**.

Invalid configuration aborts execution.

---

### Registry

**Definition:**  
The in-memory, validated representation of configuration.

The registry:
- Is read-only
- Is deterministic
- Contains no runtime state

All execution decisions are based on the registry.

---

### Guardrails

**Definition:**  
Explicit safety constraints applied before execution.

Examples:
- Requiring confirmation for sensitive roles
- Blocking ambiguous actions
- Enforcing region restrictions

Guardrails prevent unsafe execution, not unsafe users.

---

### Sensitive Role

**Definition:**  
An IAM role whose use carries elevated risk.

Sensitive roles:
- Require explicit confirmation
- Are never auto-selected
- Are visible by design

Sensitivity is a policy decision, not an AWS concept.

---

## Execution Concepts

### Execution

**Definition:**  
A single invocation of awsctl resulting in zero or more AWS API calls.

Executions are:
- Stateless
- Short-lived
- Explicit

There is no background execution.

---

### Failure

**Definition:**  
A terminal condition where awsctl refuses to proceed.

Failure is often intentional and protective.

Failure always:
- Aborts execution
- Leaves no partial state
- Surfaces a clear reason

---

### Abort

**Definition:**  
A controlled termination of execution.

Aborts are safe outcomes.
User-initiated aborts are not errors.

---

### Determinism

**Definition:**  
Given the same inputs, awsctl produces the same behavior.

Determinism is required for:
- Safety
- Auditability
- Predictability

Implicit defaults violate determinism.

---

## Environment & UX Concepts

### Context

**Definition:**  
The currently selected AWS account, role, and region.

Context exists only:
- In memory
- In the user’s shell (if explicitly exported)

Context is not persisted by awsctl.

---

### Shell Integration

**Definition:**  
An optional mechanism for exporting credentials into a shell session.

Shell integration:
- Is opt-in
- Is explicit
- Is reversible

awsctl never modifies shell startup files automatically.

---

### Interactive Mode

**Definition:**  
A mode where awsctl prompts the user for confirmation or selection.

Interactivity is a safety feature, not a convenience feature.

---

## Extension Concepts

### Plugin

**Definition:**  
An optional extension that integrates external systems or behaviors.

Plugins:
- Are untrusted
- Are explicitly enabled
- Cannot bypass policy
- Fail closed

---

### Plugin Boundary

**Definition:**  
The isolation boundary between core awsctl logic and plugin code.

Crossing this boundary requires explicit contracts.

---

## Security & Trust Concepts

### Trust Boundary

**Definition:**  
A point where control, authority, or responsibility changes.

Key trust boundaries in awsctl:
- User ↔ IdP
- awsctl ↔ AWS
- Core ↔ Plugins
- Configuration ↔ Execution

Trust boundaries are explicit and documented.

---

### Root of Trust

**Definition:**  
The minimal set of assumptions awsctl relies on.

For awsctl:
- Identity Provider authentication
- AWS STS enforcement
- Declarative configuration validity

Nothing else is trusted implicitly.

---

### Least Privilege

**Definition:**  
Granting only the minimum permissions required.

awsctl enforces least privilege by:
- Hiding unapproved roles
- Refusing implicit access
- Surfacing scope clearly

---

## Anti-Terms (Explicitly Discouraged)

The following terms are discouraged because they create ambiguity:

- “Login” (use *authenticate* or *assume role*)
- “Session” (use *execution* or *context*)
- “Magic” (describe the actual behavior)
- “Convenience” (state the tradeoff explicitly)

---

## Relationship to Other Documents

This document underpins:

- **Security Overview**
- **Trust and Security Boundaries**
- **Configuration Schema**
- **Developer Architecture Guide**
- **Failure Modes & Mitigation**

Terminology defined here is binding across all of them.

---

## Summary

awsctl is intentionally explicit.

Clear language enables:
- Correct usage
- Safe extension
- Accurate review
- Reliable audits

If a term is unclear, update this document first.

This is the vocabulary contract for awsctl.
