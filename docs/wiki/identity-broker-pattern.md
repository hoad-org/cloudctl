# identity-broker-pattern

# 🆔 Identity Broker Pattern

This document defines the **Identity Broker Pattern** as implemented by `awsctl`. It explains what an identity broker is, what `awsctl` brokers, why this pattern is safer than alternatives, and how it scales in large organizations.

This document is authoritative.

---

## 🏗️ Core Definition

An **identity broker** is a system that connects proven identity to existing authority in a controlled, auditable way.



**A broker strictly:**
* Does **not** authenticate users.
* Does **not** store credentials.
* **Does not** grant permissions or own authority.

`awsctl` is an identity broker.

---

## 🎯 Why Identity Brokering Exists

In large AWS organizations, the challenge is not authentication, but **translation**. Organizations struggle to safely translate authenticated humans into *intended* AWS actions without falling into risks like static credentials or unreviewed privilege escalation.

`awsctl` solves **translation**, not authentication. It ensures that when a human attempts to use their identity, the resulting AWS session is scoped, guarded, and intended.

---

## 🔍 What awsctl Brokers (and Does Not Broker)

| awsctl Brokers (Context) | awsctl DOES NOT Broker (Authority) |
| :--- | :--- |
| **Proven Identity** (Who the human is) | **Authentication** (Passwords/MFA) |
| **Allowed Roles** (Registry constraints) | **Authorization** (IAM Policy definitions) |
| **Guardrails** (Conditions & Regions) | **Permissions** (What the role can do) |
| **Session Logic** (For how long) | **Trust Relationships** (IAM Role Trust) |

---

## 🔄 High-Level Identity Flow

`awsctl` sits between proof and power, ensuring the handshake between the Identity Provider (IdP) and AWS STS is governed by organizational policy.



### 🛰️ Identity Brokerage (Mermaid)

```mermaid
sequenceDiagram
    participant Human
    participant IdP
    participant awsctl
    participant AWS

    Human->>IdP: Authenticate (MFA)
    IdP-->>awsctl: Proof of Identity
    awsctl->>awsctl: Validate intent & policy
    awsctl->>AWS: AssumeRole (STS)
    AWS-->>awsctl: Temporary credentials
```

---

## 🛡️ Why This Pattern Is Safer

* **Vs. Static Credentials:** No long-lived secrets, no credential sprawl, and automatic expiration.
* **Vs. Direct Role Switching:** Enforces guardrails, validates intent, and gates sensitive roles.
* **Vs. Custom Auth Systems:** No new trust roots, no duplicated security logic, and no shadow identity plane.

---

## 🌓 Identity vs. Authority Separation

`awsctl` enforces a strict separation of concerns. Breaking this separation creates systemic risk.

| Concern | Owner |
| :--- | :--- |
| **Authentication** | Identity Provider (IdP) |
| **Authorization** | AWS IAM |
| **Intent Validation** | `awsctl` |
| **Execution** | AWS STS |



### 🏗️ Identity Broker Boundary (Diagram-as-Code)

```mermaid
graph LR
    IdP[Identity Provider]
    Broker[awsctl Identity Broker]
    STS[AWS STS]
    Role[Target IAM Role]

    IdP --> Broker
    Broker --> STS
    STS --> Role
```
*`awsctl` never becomes a trust anchor; it is a pass-through validator.*

---

## ✅ Broker Constraints (Non-Negotiable)

To maintain the security posture, an identity broker must:
1.  **Be stateless:** No local database of users or roles.
2.  **Be ephemeral:** Exists only for the duration of the request.
3.  **Fail closed:** If brokering fails, no credentials are issued.
4.  **Leave audit trails intact:** Native AWS and IdP logs must remain the source of truth.
5.  **Be removable:** Deleting `awsctl` must not break the underlying security model.

---

## 📈 Scaling the Pattern

This pattern scales horizontally because:
* **External Identity:** Identity management remains with the enterprise IdP.
* **External Authority:** Permissions remain in AWS IAM.
* **Local Logic:** Broker logic runs on the operator's workstation, removing central bottlenecks.
* **Declarative Policy:** All guardrails are defined in a version-controlled registry.

---

## ⚖️ Summary

The Identity Broker Pattern is powerful because it is limited. `awsctl` brokers identity just enough to make access safe, and no more. If `awsctl` ever becomes an authentication system or a source of authority, it has violated this pattern.
