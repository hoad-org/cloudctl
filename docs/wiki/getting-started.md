# 🚀 Getting Started

This page provides a **minimal, safe introduction** to `awsctl`. It is intentionally limited; `awsctl` is a security-sensitive tool, and this page is not a general tutorial.

---

## 🏗️ What awsctl Is

`awsctl` is a **client-side identity broker** for AWS, Microsoft Azure, and Google Cloud Platform. It helps humans select approved accounts and assume short-lived credentials safely while enforcing organizational guardrails.



**Key Constraints:**
- **No Authentication:** `awsctl` does not authenticate users.
- **No Persistence:** It does **not** store credentials on disk.
- **No Authority:** It does **not** grant permissions or replace IAM.

---

## 📋 Prerequisites

Before using `awsctl`, you must already possess the underlying authority:

* Access to your organization’s **Identity Provider** (e.g., AWS IAM Identity Center).
* At least one **AWS role** you are permitted to assume.
* **MFA** properly configured at the identity source.
* Network access to **AWS STS** endpoints.

**For Azure orgs:** Azure CLI (`az`) installed and authenticated via `az login`.
**For GCP orgs:** gcloud SDK installed and authenticated via `gcloud auth login`.

`awsctl` will not create or fix these foundational requirements.

---

## 📥 Installation

Install `awsctl` using the approved method for your specific environment.

**Example (macOS, Homebrew):**
```bash
brew install awsctl
```

**Verify installation:**
```bash
awsctl version
awsctl doctor
```
> [!CAUTION]
> If `awsctl doctor` reports any errors, **do not proceed**. Resolve environmental issues first.

---

## 🚦 Your First Safe Command

Start with a read-only command to verify your local configuration:

```bash
awsctl status
```

This command confirms `awsctl` can see your identity context **without** changing AWS state or modifying your local environment variables.

---

## 🔄 Switching Context (Carefully)

To transition into an AWS account or role:

```bash
awsctl switch
```



**The Broker Sequence:**
1.  `awsctl` displays available accounts and roles based on your identity.
2.  It prompts for confirmation when risk is elevated (e.g., sensitive accounts).
3.  It emits short-lived credentials only after policy validation.
**Nothing happens silently.**

```Mermaid
sequenceDiagram
    autonumber
    actor User as Engineer
    participant CLI as awsctl
    participant Cache as ~/.aws/sso/cache
    participant Browser as System Browser
    participant AWS as AWS Identity Center
    participant STS as AWS STS
    participant Cloud as Target Account

    Note over User, Cloud: Phase 1: Authentication (If needed)

    User->>CLI: awsctl use production
    CLI->>Cache: Check for valid SSO Access Token

    alt Token Missing or Expired
        CLI->>Browser: Launch Device Authorization URL
        Browser->>AWS: User logs in via IdP (Okta/Entra)
        AWS-->>Browser: Auth Success
        AWS->>Cache: Write new Access Token (JSON)
        CLI-->>User: "Authentication Complete"
    else Token Valid
        CLI->>Cache: Read cached Access Token
    end

    Note over User, Cloud: Phase 2: Authorization & Access

    CLI->>STS: get-caller-identity / assume-role
    STS-->>CLI: Return Temp Credentials (AccessKey/Secret)

    opt Shell Mode (EVAL)
        CLI->>User: Export AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
    end

    User->>Cloud: Run commands (terraform, kubectl, aws)
    Cloud-->>User: Execute with Assumed Role
```
---

## 🐚 Shell Integration (Optional)

Shell integration is optional, explicit, and process-scoped. To enable the session wrapper:

```bash
source <(awsctl shell init)
```
*Note: This does not modify `.zshrc` or `.bashrc` startup files.*

---

## 📚 Where to Go Next

* [[Security Overview|Security-Overview]]
* [[Identity Broker Pattern|Identity-Broker-Pattern]]
* [[CLI Overview|CLI-Overview]]
* [[Runbook|Runbook]]

> [!IMPORTANT]
> **If Something Feels Unclear:** Stop. `awsctl` is designed to be explicit. If behavior feels surprising or opaque, consult the authoritative documentation before proceeding. This friction is a security feature, not a limitation.
