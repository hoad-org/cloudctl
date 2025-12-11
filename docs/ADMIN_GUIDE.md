# file: docs/ADMIN_GUIDE.md
# Administrator Guide

This guide describes how platform, security, and cloud foundation teams manage and control `awsctl` across an engineering organization.
`awsctl` follows a **Registry-backed Hydration Model**.
This means the authoritative definitions of organizations, URLs, regions, and guardrails live centrally in the Registry (either Embedded or Remote).

---

## 1. Architecture Overview

### 1.1 User Enablement File (`~/.awsctl/orgs.yaml`)

**Scope:** User preference & **Manual Configuration (Pilot)**
**Content:** Lists enabled orgs and full definitions (during Pilot).

> enabled_orgs:
>   - btavm
>
> # Pilot Phase: Manual Definition
> orgs:
>   - name: btavm
>     sso_start_url: "https://d-9067dbbf5a.awsapps.com/start"
>     ...

### 1.2 Corporate Registry (Future State)
**Scope:** Immutable policy (Source of Truth)
Currently, `src/awsctl/registry.py` contains a **Placeholder**.
The authoritative configuration is hosted on [Confluence](https://beyondtrust.atlassian.net/wiki/x/CgD9qw).

---

## 2. Registry Strategy (Tiered Security)

You can deploy `awsctl` configuration in three ways:

| Tier | Type | Config Location | Security | Best For |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Embedded** | Compiled in binary | 🔒 High | Small teams, static configs |
| **2** | **HTTPS** | JSON on S3/Web | 🔒 Medium | Internal Corp Networks |
| **3** | **Signed** | JSON + `.minisig` | 🔒 **Critical** | Zero Trust / Public Internet |

### 2.1 Tier 3: GitOps Workflow (Recommended)

1.  **Repo:** Host `registry.json` in a private GitHub repo.
2.  **Pipeline:** On merge to `main`, sign the JSON using `minisign` and a secured private key.
3.  **Publish:** Upload `registry.json` and `registry.json.minisig` to a public-read S3 bucket.
4.  **Client:** Users simply configure the `url` in `orgs.yaml`.
    - **Trust Anchor:** The Minisign **Public Key** is pinned inside the `awsctl` binary (`src/awsctl/registry.py`).
    - **Security:** Even if a user's `orgs.yaml` is compromised, the client will **reject** any payload not signed by your private key.

---

## 3. Release Workflow (Tier 1 - Embedded)

If using the Embedded Registry strategy (or updating core application logic):

1. Modify Registry/Code: `vim src/awsctl/registry.py`
2. **[PATCH] Run full CI suite (Mandatory Security Checks):**
   - `make lint`
   - `make typecheck`
   - `make security` (Bandit/Pip-Audit)
   - `make test`
3. Commit: `git commit -m "chore(registry): update prod guardrails"`
4. Tag release: `git tag -a v2.8.1; git push origin v2.8.1`
5. Developers upgrade: `pipx upgrade awsctl`

---

## 4. Security Policy & Guardrails

### 4.1 Region Restrictions

Definition:

> "allowed_regions": ["eu-west-1"]

Enforced during `login`, `switch`, and `exec`.
Violations return `exit code: 1` immediately.

### 4.2 Role Ordering

Definition:

> "preferred_roles": ["ReadOnlyAccess"]

Promotes least-privilege roles to the top of the fuzzy selector.

### 4.3 Plugin Enforcement

Defined in `plugins`.
Runs before login. If a plugin fails (e.g., VPN check), login aborts.

### 4.4 Namespace Enforcement

All plugins must reside in `awsctl.plugins.*`. Arbitrary code execution via other namespaces is blocked.

### 4.5 TTY Guard (Operational Safety)

The binary detects if it is running in an interactive terminal during an export operation.
If detected, it refuses to print credentials to the screen.
This operational control applies to **`awsctl switch`** and **`awsctl exec`** when the binary is incorrectly run directly.

### 4.6 Break Glass Audit (v2.5+)

Definition:

> "sensitive_roles": ["AdministratorAccess"]

Behavior:

- When a user selects this role, `awsctl` halts.
- Prompts: `Justification (Ticket # / Reason):`.
- Logs the response to `~/.awsctl/audit.log` (and CloudTrail via session tags).

### 4.7 Client Version Enforcement (v2.5+)

Definition:

> "min_client_version": "2.8.1"

Behavior:
Blocks login if the client binary is older than the policy.
Forces `pipx upgrade`.
