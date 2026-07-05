# CLAUDE.md — cloudctl developer guide (for AI agents and humans)

> **This file describes the tool as it actually is.** An earlier version of this
> file described a fictional BeyondTrust product (v5.1.0, "654 tests",
> `bt-avm`/`fdr-gvc` orgs, `/Users/choad` paths). None of that was real. If you
> find a claim here that the code contradicts, trust the code and fix this file.

## What cloudctl is

**Injects short-lived credentials into a child process — no SSO profiles
written, nothing stored on disk, one command shape for AWS/GCP/Azure — built to
be driven by agents/scripts.**

Its one job is: vend short-lived credentials for an org/account/role and inject
them into a child process so you can run a CLI command or script — **without
managing static SSO profiles**.

- Version: `1.0.0b0` (see `src/cloudctl/_version.py` / `pyproject.toml`).
- Package name: `cloudctl`. Installed editable from this repo.
- It is optimised for **agentic (non-interactive) use**: it must never hang on a
  prompt, must emit machine-parseable output on request, and must be fully
  driveable from flags with no prior shell state.

**Vocabulary map:** `--account` = AWS account / GCP project / Azure
subscription; `--role` = **AWS only** (a no-op on GCP/Azure).

## Real configuration (this machine)

- Org config: `~/.config/cloudctl/orgs.yaml`
- Active context: `~/.config/cloudctl/current_context.json` (**single source of
  truth** — there is no `~/.cloudctl/context.json`; older code read that phantom
  path and it has been aliased away).
- AWS SSO token cache: `~/.aws/sso/cache/` (standard AWS location).

Configured orgs:

| Org | Provider | Notes |
|-----|----------|-------|
| `myorg` | AWS | IAM Identity Center, **SSO region `eu-west-2`**, partition `aws` |
| `gcp-terrorgems` | GCP | project `asatst-gemini-api-v2`, ADC auth |
| `azure-craighoad` | Azure | subscription/tenant configured |

## The commands that matter

Primary verbs are **`run`** and **`whoami`**. (`exec` is a hidden back-compat
alias for `run`; `status`/`env` for `whoami`; `list-roles` for `roles`. Use the
primary verbs.)

```bash
cloudctl login <org>                 # authenticate SSO; records the org into context
cloudctl whoami --format json        # LIVE, verified identity as JSON (agent-parseable)
cloudctl accounts <org> --format json
cloudctl roles <org> --account <id> --format json
cloudctl switch <org> --account <id> --role <role> --region <region> --non-interactive
cloudctl run --org <org> --account <id> --role <role> --region <region> -- <command...>
```

### The one canonical agent form (stateless, no prior context needed)

```bash
cloudctl run --org myorg --account 123456789012 --role AdministratorAccess \
  --region us-east-1 -- aws sts get-caller-identity
```

Notes an agent must know:
- **`run` requires a literal `--`** before the child command, or argparse will
  eat flags like `--query`/`--output`. Everything after `--` goes to the child
  verbatim.
- `--region` on `run`/`switch` is the region the **executed command** runs in.
  Internally, the SSO `get-role-credentials` portal call uses the org's
  `sso_region` (e.g. `eu-west-2`), never this value. The region you pass is
  injected as `AWS_REGION`/`AWS_DEFAULT_REGION` into the child.
- No `AWS_PROFILE` is ever set. The injected STS keys are self-contained.
- `run` is non-interactive by nature; in a non-TTY context it fails fast asking
  for explicit `--account/--role/--region` instead of prompting. Break-glass on
  a sensitive role reads `CLOUDCTL_BREAK_GLASS_REASON` from the env.

## Provider credential injection (honest)

- **AWS** (`providers/aws.py`): real STS keys via SSO `get-role-credentials`
  (portal call in `org.sso_region`). Failures are **classified faithfully** —
  AUTH (2) / DENIED (4) / NOT_FOUND (3) are distinguished from stderr, so a
  `Forbidden` is DENIED, not a phantom "no SSO session". `get_identity()` does a
  live `sts get-caller-identity`.
- **GCP** (`providers/gcp.py`): `run -- gcloud …` works —
  `CLOUDSDK_AUTH_ACCESS_TOKEN` makes the child `gcloud` run under the injected,
  non-mutating token (plus `CLOUDSDK_CORE_PROJECT`). **`gsutil`, `bq`, and
  standard ADC libraries do NOT honor that var** — a bare `gsutil`/`bq` may run
  under the ambient login. `--role` is a **no-op** on GCP (permissions come from
  the IAM policy bound to the identity). No global `gcloud config set`.
- **Azure** (`providers/azure.py`): `run -- terraform …` works via the `ARM_*`
  set (`ARM_USE_CLI=false` when a token is present). The **bare `az` CLI is only
  injected when the org supplies service-principal creds** (`client_id` +
  `client_secret` + `tenant_id` → `AZURE_CLIENT_*`, which `az` honors) —
  `az_uses_injected_identity()` reports exactly this. Otherwise the exec layer
  **WARNS** and pins `--subscription <account>`, and `az` runs under the ambient
  `az login`. `--role` is a **no-op** on Azure. No global `az account set`.

## whoami reports real identity

`whoami` calls each provider's honest `get_identity()` — a **live** cloud query
(`sts get-caller-identity`, `gcloud auth list` + project, `az account show`). It
reports what the cloud says, or `identity: null` when the session is
missing/expired. It **never** fabricates an identity from stored context. The
`--format json` payload is
`{provider, org, account, role, region, identity, expires_at,
expires_in_seconds}` (`expires_*` may be `null`).

## Exit codes (`exit_codes.py`)

`OK=0`, `ERROR=1`, `AUTH=2`, `NOT_FOUND=3`, `DENIED=4`, `USAGE=5`. Argparse /
usage errors (including a missing `--` before the child command) are **USAGE
(5)**, not AUTH (2).

## Architecture

```
src/cloudctl/
  cli.py            # arg parser (_build_parser) + dispatch (_DISPATCH) + handlers
  core.py           # login/exec/logout core logic
  context_manager.py# active-context persistence (current_context.json)
  use_exports.py    # AWS export-line generation (switch/eval path)
  providers/        # aws.py, gcp.py, azure.py, base.py — get_credentials contract
  commands/         # per-command executors (exec, accounts, init, org, ...)
  guardrails.py     # allowed-roles / break-glass / audit (no-hang under non-TTY)
  config.py         # orgs.yaml load/save
```

Two things to keep in mind:
- The **live** `run` path is `cli.cmd_exec → commands/exec.py::ExecCommand →
  providers/*.py::get_credentials`. (`core.py::cmd_exec` + `use_exports` is a
  parallel path used by the switch/eval flow and some tests.)
- The parser is authoritative in `cli.py::_build_parser`. The
  `configure_parser()` methods inside `commands/*.py` are **not** wired in.

## Testing

```bash
python -m pytest -q          # full suite
```

Do not hardcode a test count in docs — it drifts. Add a real, behavioural test
when you fix a bug: the credential bugs had **no** direct test, which is why they
survived. See `tests/test_providers.py::TestAwsProviderCredentials` for the
pattern.

## Backlog

### Done (agent-first overhaul)

- **Faithful errors** — providers classify the real cause (AUTH/DENIED/
  NOT_FOUND) instead of flattening everything to "no SSO session".
- **Real `whoami`** — live identity query, `identity: null` when unverifiable,
  never fabricated; JSON includes `expires_at`/`expires_in_seconds`.
- **Roles provider dispatch** — `roles` routes through each provider's
  `list_roles`.
- **Azure `az` safety** — warn + pin `--subscription` when SP creds are absent;
  inject `AZURE_CLIENT_*` only when they're present.
- **Provider-aware `--role`** — required for AWS, a no-op for GCP/Azure; a
  missing role never blocks a GCP/Azure command.
- **Exit-code fixes** — `AUTH=2/NOT_FOUND=3/DENIED=4/USAGE=5` emitted at the
  right sites; usage errors are `5`, not `2`.
- **Value/vocab help** — `run --help` and top-level help state the benefit and
  the `--account`/`--role` vocabulary map.
- **Zero-disk `--no-cache` mode** — `run --no-cache` authenticates in memory and
  vends STS without cloudctl ever writing the SSO token. AWS token acquisition
  (`_obtain_sso_token`) is split from caching; `authenticate_in_memory()` +
  `get_credentials(token=…)` power the path. GCP/Azure: no-op (their tokens are
  owned by gcloud/az).

### Open / known limits

- **Credential storage is opt-out, not absent.** By default the SSO access token
  is cached in the standard `~/.aws/sso/cache/` (`0o600`, same file the AWS CLI
  writes) for session reuse; the vended STS keys are never persisted. Use
  `run --no-cache` for zero credentials on disk (in-memory auth).
- **GCP service-account impersonation** and a **machine-readable capabilities
  index** are deliberately **out of the thin-wrapper scope** for now.
- **Verb redundancy** — `login`/`switch`/`use` + the read verbs still overlap; a
  future breaking pass could collapse them further.
- Removed: dead `skills/` tree, `pricing`, `watch`, `okta` plugin,
  `encryption.py` (AES-256 over public SSO start URLs — security theatre), and
  the interactive `wizard/` (`init` is now a non-interactive config
  initializer).

## Golden rules when changing this tool

1. **Never hang.** Any interactive prompt must gate on a non-interactive check
   (`cli._non_interactive`) and fail fast with an actionable message.
2. **Never set `AWS_PROFILE`** or write static profiles. Inject env only.
3. **SSO portal calls use `org.sso_region`**, command execution uses the user's
   `--region`. Don't conflate them.
4. **Never fabricate an identity.** `whoami`/`get_identity` must query the cloud
   or return null.
5. **Verify against reality**, not just tests — run the real `cloudctl` command
   and check the output, because the test suite has historically been green
   while the tool was broken.
