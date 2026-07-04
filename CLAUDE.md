# CLAUDE.md — cloudctl developer guide (for AI agents and humans)

> **This file describes the tool as it actually is.** An earlier version of this
> file described a fictional BeyondTrust product (v5.1.0, "654 tests",
> `bt-avm`/`fdr-gvc` orgs, `/Users/choad` paths). None of that was real. If you
> find a claim here that the code contradicts, trust the code and fix this file.

## What cloudctl is

A multi-cloud identity/context manager whose **one job** is: vend short-lived
credentials for an org/account/role and inject them into a child process so you
can run a CLI command or script — **without managing static SSO profiles**.

- Version: `1.0.0b0` (see `src/cloudctl/_version.py` / `pyproject.toml`).
- Package name: `cloudctl`. Installed editable from this repo.
- It is optimised for **agentic (non-interactive) use**: it must never hang on a
  prompt, must emit machine-parseable output on request, and must be fully
  driveable from flags with no prior shell state.

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

```bash
cloudctl login <org>                 # authenticate SSO; now also records the org into context
cloudctl status --format json        # active context as JSON (agent-parseable)
cloudctl accounts <org> --format json
cloudctl list-roles <org> --account <id> --format json
cloudctl switch <org> --account <id> --role <role> --region <region> --non-interactive
cloudctl exec --org <org> --account <id> --role <role> --region <region> -- <command...>
```

### The one canonical agent form (stateless, no prior context needed)

```bash
cloudctl exec --org myorg --account 123456789012 --role AdministratorAccess \
  --region us-east-1 -- aws sts get-caller-identity
```

Notes an agent must know:
- **`exec` requires a literal `--`** before the child command, or argparse will
  eat flags like `--query`/`--output`.
- `--region` on `exec`/`switch` is the region the **executed command** runs in.
  Internally, the SSO `get-role-credentials` portal call uses the org's
  `sso_region` (e.g. `eu-west-2`), never this value. The region you pass is
  injected as `AWS_REGION`/`AWS_DEFAULT_REGION` into the child.
- No `AWS_PROFILE` is ever set. The injected STS keys are self-contained.
- In a non-TTY / CI / agent context, `switch` will **not** prompt — it fails
  fast asking for explicit `--account/--role/--region`. Break-glass on a
  sensitive role reads `CLOUDCTL_BREAK_GLASS_REASON` from the env instead of
  prompting.

## Provider credential injection (Phase 3)

- **AWS**: real STS keys via SSO `get-role-credentials` (portal call in
  `org.sso_region`). `providers/aws.py`.
- **GCP**: sets `CLOUDSDK_AUTH_ACCESS_TOKEN` (honored by the `gcloud` CLI) plus
  `CLOUDSDK_CORE_PROJECT`; no global `gcloud config set`. `--role` is **not** a
  functional credential selector on GCP (static IAM). `providers/gcp.py`.
- **Azure**: emits the `ARM_*` set with `ARM_USE_CLI=false` when a token is
  present (targets the Terraform azurerm provider / SDKs, not the bare `az`
  CLI); no global `az account set`. `providers/azure.py`.

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
- The **live** `exec` path is `cli.cmd_exec → commands/exec.py::ExecCommand →
  providers/aws.py::get_credentials`. (`core.py::cmd_exec` + `use_exports` is a
  parallel path used by the switch/eval flow and some tests.)
- The parser is authoritative in `cli.py::_build_parser`. The
  `configure_parser()` methods inside `commands/*.py` are **not** wired in.

## Testing

```bash
python -m pytest -q          # full suite
```

Do not hardcode a test count in docs — it drifts (the old file claimed both
"431" and "654"; reality was ~734, then features were removed). Add a real,
behavioural test when you fix a bug: the two credential bugs above had **no**
direct test, which is why they survived. See
`tests/test_providers.py::TestAwsProviderCredentials` for the pattern.

## Known remaining work (honest backlog)

- **Verb redundancy**: `login`/`switch`/`use`/`exec` + `status`/`env`/`whoami`
  overlap. `use` == `switch`. A future pass should collapse these.
- **Output contract**: `--format json` works for `status`/`env`/`accounts`/
  `list-roles`; `whoami` and `exec` have no JSON mode yet. Console output still
  goes to stdout in places it should go to stderr.
- **Exit codes**: the documented 2/3/4/5 scheme is only partially emitted.
- **Bloat still present**: `encryption.py` (AES-256 over public SSO start URLs —
  security theatre, wired into `config.py` load/save) and `wizard/` (~863 LOC,
  tied to `init`) are candidates for removal but are entangled with critical
  paths; cut them carefully with tests.
- Removed already: dead `skills/` tree, `pricing`, `watch`, `okta` plugin.

## Golden rules when changing this tool

1. **Never hang.** Any interactive prompt must gate on a non-interactive check
   (`cli._non_interactive`) and fail fast with an actionable message.
2. **Never set `AWS_PROFILE`** or write static profiles. Inject env only.
3. **SSO portal calls use `org.sso_region`**, command execution uses the user's
   `--region`. Don't conflate them.
4. **Verify against reality**, not just tests — run the real `cloudctl` command
   and check the output, because the test suite has historically been green
   while the tool was broken.
