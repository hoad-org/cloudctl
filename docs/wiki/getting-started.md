# 🚀 Getting Started

This page provides a **minimal, safe introduction** to `cloudctl`. It is intentionally limited; `cloudctl` is a security-sensitive tool, and this page is not a general tutorial.

---

## 🏗️ What cloudctl Is

`cloudctl` is a **client-side identity broker** for AWS, Microsoft Azure, and Google Cloud Platform. It helps humans select approved accounts and assume short-lived credentials safely while enforcing organizational guardrails.



**Key Constraints:**
- **No Authentication:** `cloudctl` does not authenticate users.
- **No Persistence:** It does **not** store credentials on disk.
- **No Authority:** It does **not** grant permissions or replace IAM.

---

## 📋 Prerequisites

Before using `cloudctl`, you must already possess the underlying authority:

* Access to your organization’s **Identity Provider** (e.g., AWS IAM Identity Center).
* At least one **AWS role** you are permitted to assume.
* **MFA** properly configured at the identity source.
* Network access to **AWS STS** endpoints.

**For Azure orgs:** Azure CLI (`az`) installed and authenticated via `az login`.
**For GCP orgs:** gcloud SDK installed and authenticated via `gcloud auth login`.

`cloudctl` will not create or fix these foundational requirements.

---

## 📥 Installation

Install `cloudctl` using the approved method for your specific environment.

**Example (macOS, Homebrew):**
```bash
brew install cloudctl
```

**Verify installation:**
```bash
cloudctl version
cloudctl doctor
```
> [!CAUTION]
> If `cloudctl doctor` reports any errors, **do not proceed**. Resolve environmental issues first.

---

## 🚦 Your First Safe Command

Start with a read-only command to verify your local configuration:

```bash
cloudctl status
```

This command confirms `cloudctl` can see your identity context **without** changing AWS state or modifying your local environment variables.

---

## 🔄 Switching Context (Carefully)

To transition into an AWS account or role:

```bash
cloudctl switch
```



**The Broker Sequence:**
1.  `cloudctl` displays available accounts and roles based on your identity.
2.  It prompts for confirmation when risk is elevated (e.g., sensitive accounts).
3.  It emits short-lived credentials only after policy validation.
**Nothing happens silently.**

```Mermaid
sequenceDiagram
    autonumber
    actor User as Engineer
    participant CLI as cloudctl
    participant Cache as ~/.aws/sso/cache
    participant Browser as System Browser
    participant AWS as AWS Identity Center
    participant STS as AWS STS
    participant Cloud as Target Account

    Note over User, Cloud: Phase 1: Authentication (If needed)

    User->>CLI: cloudctl use production
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

Shell integration is **opt-in**. To install the shell wrapper so that `cloudctl switch` and `cloudctl use` export credentials into the current shell:

```bash
cloudctl init
```

This injects a small wrapper function into your `.bashrc`, `.zshrc`, or equivalent profile file (with your explicit confirmation). For shell tab-completion, run:

```bash
cloudctl completion --install
```

Both operations can be reviewed and reversed at any time with `cloudctl uninstall`.

---

## 📚 Where to Go Next

* [[Security Overview|Security-Overview]]
* [[Identity Broker Pattern|Identity-Broker-Pattern]]
* [[CLI Overview|CLI-Overview]]
* [[Runbook|Runbook]]

> [!IMPORTANT]
> **If Something Feels Unclear:** Stop. `cloudctl` is designed to be explicit. If behavior feels surprising or opaque, consult the authoritative documentation before proceeding. This friction is a security feature, not a limitation.
