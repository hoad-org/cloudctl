# cloudctl — ephemeral multi-cloud credential runner

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Injects short-lived credentials into a child process — no SSO profiles
written, nothing stored on disk, one command shape for AWS/GCP/Azure — built to
be driven by agents/scripts.**

`cloudctl` vends short-lived credentials for an org/account/role across AWS,
GCP, and Azure and runs your command with them injected as environment
variables. It is non-interactive by nature, flag-driven, and machine-parseable.

**Vocabulary map** (one shape, three clouds):

| cloudctl flag | AWS | GCP | Azure |
|---------------|-----|-----|-------|
| `--account`   | account ID | project ID | subscription ID |
| `--role`      | permission set (required) | **no-op** | **no-op** |

> Status: `1.0.0b0` (beta). This README describes the tool as it actually
> behaves. Features are only listed here if they work.

---

## Install

Editable install from this repo:

```bash
python3.12 -m pip install -e .
cloudctl doctor        # sanity-check the install and config
```

Configuration lives at `~/.config/cloudctl/orgs.yaml`. The active context is
stored at `~/.config/cloudctl/current_context.json`. AWS SSO tokens use the
standard `~/.aws/sso/cache/`.

---

## Quick start

```bash
# 1. Authenticate an org's SSO session (opens a browser)
cloudctl login myorg

# 2. See the active identity (live query; JSON for scripts/agents)
cloudctl whoami --format json

# 3. Run a command with credentials injected — stateless, no prior switch
cloudctl run --org myorg --account 123456789012 --role AdministratorAccess \
  --region us-east-1 -- aws sts get-caller-identity
```

`run` is the canonical form for automation: it takes everything on the command
line and needs no persisted context. (`exec` is a hidden back-compat alias for
`run`, and `status`/`env` for `whoami`; use `run`/`whoami` in new work.)

---

## The agent contract (things to know)

- **`run` needs a literal `--`** before the child command, or the parser will
  consume flags like `--query`/`--output` meant for the child. Everything after
  `--` is passed to the child verbatim.
- **`--region` is the region the *child command* runs in.** It is injected as
  `AWS_REGION`/`AWS_DEFAULT_REGION`. Internally the SSO `get-role-credentials`
  call uses the org's own `sso_region` — the two are not the same value and are
  no longer conflated (that bug caused "session token not found" across
  regions).
- **No `AWS_PROFILE` is ever set.** The injected STS keys are self-contained; a
  profile name would shadow them and break the child command.
- **Never hangs.** `run` is non-interactive by nature; in a non-TTY context it
  fails fast asking for explicit `--account/--role/--region` instead of showing
  a picker. A sensitive-role justification is read from
  `CLOUDCTL_BREAK_GLASS_REASON`.

---

## Multi-cloud behaviour (honest)

| Cloud | What actually happens |
|-------|-----------------------|
| **AWS** | Real STS keys via SSO `get-role-credentials` (portal call in the org's `sso_region`). Errors are faithful: AUTH / DENIED / NOT_FOUND are distinguished (a `Forbidden` is DENIED, not "no SSO session"). `--json-errors` prints `{"error","code"}`. |
| **GCP** | `run -- gcloud …` works: `CLOUDSDK_AUTH_ACCESS_TOKEN` makes the child `gcloud` run under the injected, non-mutating token (plus `CLOUDSDK_CORE_PROJECT`). **`gsutil`, `bq`, and standard ADC client libraries do NOT honor this token** — a bare `gsutil`/`bq` may still run under the ambient login. `--role` is a **no-op** on GCP (permissions come from the IAM policy bound to the identity). No global `gcloud config set`. |
| **Azure** | `run -- terraform …` works via the `ARM_*` set (`ARM_USE_CLI=false` when a token is present). The **bare `az` CLI is only injected when the org config supplies service-principal creds** (`client_id` + `client_secret` + `tenant_id` → `AZURE_CLIENT_*`, which `az` honors). Without SP creds, `cloudctl` **WARNS** that bare `az` runs under your ambient `az login`, pins `--subscription <account>`, and lets `az` run under that ambient login. `--role` is a **no-op** on Azure. No global `az account set`. |

---

## Commands

```
run   --org --account --role --region -- <cmd...>
                            Run <cmd> with credentials injected (nothing on disk)
login <org>                 Authenticate SSO for an org (records it as context)
logout                      Clear the active context and provider session
whoami [--format json]      Show the LIVE, verified identity (never fabricated)
switch <org> [--account --role --region] [--non-interactive]
                            Set a persistent context (human convenience)
accounts <org> [--format json]      List accessible accounts
roles <org> --account <id> [--format json]   List assumable roles (AWS)
orgs | org list             List configured orgs
init | config init          Create / merge orgs.yaml
doctor                      Diagnose install and config
```

Legacy aliases kept for back-compat: `exec` → `run`, `status`/`env` → `whoami`,
`list-roles` → `roles`. Prefer the primary verbs.

---

## whoami reports real identity

`cloudctl whoami` runs a **live** identity query for the active provider
(`sts get-caller-identity`, `gcloud auth list` + project, `az account show`). It
reports what the cloud actually says — or `identity: null` if the session is
missing/expired. It **never** fabricates an identity by echoing stored context.

```bash
cloudctl whoami --format json
```

```json
{
  "provider": "aws",
  "org": "myorg",
  "account": "123456789012",
  "role": "AdministratorAccess",
  "region": "us-east-1",
  "identity": { "account": "123456789012", "arn": "...", "user_id": "..." },
  "expires_at": "2026-07-04T18:00:00Z",
  "expires_in_seconds": 7200
}
```

The JSON form always includes `expires_at` and `expires_in_seconds` (both may be
`null` when the provider can't determine expiry).

---

## Exit codes

`run` (and the read commands) use a documented, machine-checkable scheme:

| Code | Meaning |
|------|---------|
| `0`  | success (the child's own exit code is propagated verbatim on the success path) |
| `1`  | error (uncategorised failure) |
| `2`  | AUTH — authentication required (missing/expired SSO session) |
| `3`  | NOT_FOUND — invalid org / account / role |
| `4`  | DENIED — permission/access denied (the real reason, not "auth") |
| `5`  | USAGE — invalid arguments (argparse/usage errors, e.g. missing `--`) |

Note that argparse/usage errors are `5` (USAGE), not `2`.

---

## Examples

```bash
# List S3 buckets in a specific account/role, no shell state
cloudctl run --org myorg --account 123456789012 --role ReadOnly \
  --region eu-west-2 -- aws s3api list-buckets --query 'Buckets[].Name'

# Terraform against AWS with injected short-lived creds
cloudctl run --org myorg --account 123456789012 --role AdministratorAccess \
  --region eu-west-2 -- terraform plan

# GCP: gcloud runs under the injected token (--role is a no-op)
cloudctl run --org gcp-terrorgems --account my-project \
  --region europe-west1 -- gcloud storage buckets list

# Azure Terraform via ARM_* (--role is a no-op)
cloudctl run --org azure-craighoad --account <subscription-id> -- terraform plan
```

---

## Testing

```bash
python -m pytest -q
```

A green suite is necessary but **not** sufficient — historically the tests
passed while credential injection was broken. When fixing a bug, add a
behavioural test (see `tests/test_providers.py::TestAwsProviderCredentials`) and
verify against a real `cloudctl` invocation.

---

## Honest limitations

- **The SSO access token is the one credential written to disk** — the standard
  `~/.aws/sso/cache/` file (mode `0o600`), the same file the AWS CLI itself
  writes. The *vended* STS keys are never written to disk. A truly "no
  credentials on disk" mode (in-memory only / `--no-cache`) is **not yet
  implemented**.
- **GCP service-account impersonation** and a **machine-readable capabilities
  index** are deliberately out of scope for now — cloudctl stays a thin wrapper.
- The human-oriented `switch` path still depends on the shell-function wrapper
  to apply exports to an interactive shell; `run` is the wrapper-free path and
  the one agents should use.

## License

MIT — see [LICENSE](LICENSE).
