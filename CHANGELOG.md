# Changelog

All notable changes to `cloudctl` are documented here. This project uses
semantic versioning; the current version is `1.0.0b0` (beta).

## [Unreleased] — agent-first overhaul

The `overhaul/agent-first` branch refocuses the tool on non-interactive,
agent-driven use and fixes the credential spine that was silently broken.

### Fixed

- **Credential spine.** AWS credentials are now vended via a real SSO
  `get-role-credentials` portal call in the org's `sso_region`, and injected as
  self-contained STS keys. The previous conflation of the SSO region with the
  command's `--region` (which caused "session token not found" across regions)
  is resolved.
- **No `AWS_PROFILE` is ever set.** A profile name was shadowing the injected STS
  keys and breaking child commands.
- **Real multi-cloud injection.** GCP sets `CLOUDSDK_AUTH_ACCESS_TOKEN` +
  `CLOUDSDK_CORE_PROJECT`; Azure emits the `ARM_*` set with `ARM_USE_CLI=false`
  when a token is present. No global `gcloud config set` / `az account set`.
- **Context path.** `~/.config/cloudctl/current_context.json` is the single
  source of truth; the phantom `~/.cloudctl/context.json` path was aliased away.
- **Test isolation.** Fixed tests that leaked state / relied on the machine's
  real config.

### Added

- **Primary verbs `run` and `whoami`.** `run` is the canonical stateless form;
  `whoami` shows the active identity. `exec`/`status`/`env`/`list-roles` remain
  as hidden back-compat aliases.
- **Real `whoami`.** Reports the LIVE, verified identity (`sts
  get-caller-identity`, `gcloud auth list`, `az account show`) or
  `identity: null` — never fabricated. `--format json` includes `expires_at`
  and `expires_in_seconds`.
- **Faithful provider errors.** AUTH / DENIED / NOT_FOUND are distinguished from
  the provider's real failure, so a `Forbidden` is DENIED, not "no SSO session".
- **Azure `az` safety.** With no service-principal creds, `run -- az …` warns
  and pins `--subscription`; `AZURE_CLIENT_*` is injected only when SP creds are
  configured.
- **No-hang guards.** In a non-TTY / CI / agent context, `run`/`switch` fail
  fast asking for explicit `--account/--role/--region` instead of showing a
  picker. Sensitive-role justification is read from `CLOUDCTL_BREAK_GLASS_REASON`.
- **Machine-readable output.** `--format json` on `whoami`/`accounts`/`roles`
  (and their `status`/`env`/`list-roles` aliases); `--json-errors` on `run`.
- **Documented exit codes.** `OK=0`, `ERROR=1`, `AUTH=2`, `NOT_FOUND=3`,
  `DENIED=4`, `USAGE=5` (`src/cloudctl/exit_codes.py`); usage/argparse errors
  are `5`, not `2`.

### Removed

- Removed features and dead code: `pricing`, `watch`, the `okta` plugin,
  `encryption.py` (AES over public SSO start URLs — security theatre that could
  swallow config on decrypt), the interactive wizard, and the dead `skills/`
  tree.

### Docs

- Rewrote the documentation set (README, CLAUDE.md, and `docs/`) to describe the
  tool as it actually behaves, removing all fictional product/versioning claims.

### Known remaining work

See [ROADMAP.md](ROADMAP.md).
