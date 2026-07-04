# cloudctl — ephemeral multi-cloud credential runner

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

`cloudctl` vends short-lived credentials for an org/account/role across **AWS,
GCP, and Azure**, and injects them into a child process so you can run a CLI
command or script — **without managing static SSO profiles**. It is built to be
driven by AI agents and automation: non-interactive, flag-driven, and
machine-parseable.

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

# 2. See the active context (JSON for scripts/agents)
cloudctl status --format json

# 3. Run a command with credentials injected — stateless, no prior switch
cloudctl exec --org myorg --account 123456789012 --role AdministratorAccess \
  --region us-east-1 -- aws sts get-caller-identity
```

`exec` is the canonical form for automation: it takes everything on the command
line and needs no persisted context.

---

## The agent contract (things to know)

- **`exec` needs a literal `--`** before the child command, or the parser will
  consume flags like `--query`/`--output` meant for the child.
- **`--region` is the region the *child command* runs in.** It is injected as
  `AWS_REGION`/`AWS_DEFAULT_REGION`. Internally the SSO `get-role-credentials`
  call uses the org's own `sso_region` — the two are not the same value and are
  no longer conflated (that bug caused "session token not found" across
  regions).
- **No `AWS_PROFILE` is ever set.** The injected STS keys are self-contained; a
  profile name would shadow them and break the child command.
- **Never hangs.** In a non-TTY / CI / agent context, `switch` fails fast asking
  for explicit `--account/--role/--region` instead of showing a picker. A
  sensitive-role justification is read from `CLOUDCTL_BREAK_GLASS_REASON`.

### Profiles are for humans, not agents

`cloudctl` has optional named **profiles** (`cloudctl profile save/load`) as a
convenience for **humans** working interactively. They are **local-only** and
not portable — a profile stores an org/account/role pointer (never credentials)
on a single machine. **Agents should not use profiles**: pass the target
explicitly and non-interactively so execution is reproducible anywhere.

```bash
# Human, interactive — reuse a saved pointer:
cloudctl switch myorg --account 123456789012 --role ReadOnly --region eu-west-2

# Agent, explicit and non-interactive (never prompts, never depends on a profile):
cloudctl switch myorg --account 123456789012 --role ReadOnly \
  --region eu-west-2 --non-interactive
# ...or skip context entirely and just run:
cloudctl exec --org myorg --account 123456789012 --role ReadOnly \
  --region eu-west-2 -- aws s3 ls
```

---

## Multi-cloud behaviour

| Cloud | How creds are injected |
|-------|------------------------|
| AWS   | STS keys from IAM Identity Center (`get-role-credentials` in the org's SSO region) |
| GCP   | `CLOUDSDK_AUTH_ACCESS_TOKEN` (honored by `gcloud`) + `CLOUDSDK_CORE_PROJECT`; no global `gcloud config set`. `--role` is not a credential selector on GCP. |
| Azure | `ARM_*` env with `ARM_USE_CLI=false` when a token is present (targets the Terraform azurerm provider / SDKs, not the bare `az` CLI); no global `az account set`. |

---

## Commands

```
login <org>                 Authenticate SSO for an org (and record it as context)
logout                      Clear the active context and provider session
switch <org> [--account --role --region] [--non-interactive]
                            Set a persistent context (emits export lines via the shell wrapper)
exec  --org --account --role --region -- <cmd...>
                            Run <cmd> with credentials injected (no persisted state)
status | env [--format json]  Show the active context
whoami                      Show the active identity
accounts <org> [--format json]      List accessible accounts
list-roles <org> --account <id> [--format json]
orgs | org list             List configured orgs
init | setup                Create / merge orgs.yaml
doctor                      Diagnose install and config
```

---

## Examples

```bash
# List S3 buckets in a specific account/role, no shell state
cloudctl exec --org myorg --account 123456789012 --role ReadOnly \
  --region eu-west-2 -- aws s3api list-buckets --query 'Buckets[].Name'

# Terraform against AWS with injected short-lived creds
cloudctl exec --org myorg --account 123456789012 --role AdministratorAccess \
  --region eu-west-2 -- terraform plan
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

- `login`/`switch`/`use`/`exec` and `status`/`env`/`whoami` overlap; a future
  pass should collapse the verb set.
- `--format json` works for `status`/`env`/`accounts`/`list-roles`; `whoami` and
  `exec` don't have a JSON mode yet.
- The documented exit-code scheme (2/3/4/5) is only partially implemented.
- `switch` still depends on the shell-function wrapper to apply exports to your
  interactive shell; `exec` is the wrapper-free path and the one agents should
  use.

## License

MIT — see [LICENSE](LICENSE).
