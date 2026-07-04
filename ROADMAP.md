# cloudctl Roadmap

**Current version:** `1.0.0b0` (beta). This is the honest remaining backlog for
the agent-first overhaul — no enterprise/compliance items, only real work.

## Done

- **Primary verbs landed.** `run` and `whoami` are the primary verbs;
  `exec`/`status`/`env`/`list-roles` are hidden back-compat aliases.
- **Output contract for `whoami`.** `whoami --format json` emits the live
  identity plus `expires_at`/`expires_in_seconds`; `run` has `--json-errors`.
- **Exit codes wired.** `OK=0/ERROR=1/AUTH=2/NOT_FOUND=3/DENIED=4/USAGE=5` are
  emitted at the failure sites, including USAGE (5) for argparse/usage errors.
- **Faithful provider errors** and **live, non-fabricated `whoami`** across AWS,
  GCP, and Azure.

## Now

- **Collapse remaining verb overlap.** `login`/`switch`/`use` still overlap
  (`use` == `switch`). Reduce to a minimal, orthogonal set with `run` as the
  canonical stateless form — a breaking change, deliberately deferred.
- **Broaden JSON output.** A few remaining commands (e.g. `prompt`) could still
  grow a `--format json` mode.

## Next

- **Behavioural test coverage for credential injection** across all three
  providers, so the "green suite while broken" failure mode can't recur.
- **Consolidate the two `run` paths** (`cli.cmd_exec → commands/exec.py` vs
  `core.py::cmd_exec` + `use_exports`) so there is one live path.

## Later

- **"No creds on disk" mode.** The SSO access token is currently written to the
  standard `~/.aws/sso/cache/` (mode `0o600`). An in-memory-only / `--no-cache`
  mode is not yet implemented.
- **Portable, non-interactive `switch`** that doesn't depend on the shell-wrapper
  to apply exports (agents already use `run`; make the human path robust too).
- **1.0.0 (non-beta)** once the credential spine, output contract, and exit codes
  are proven against real invocations.

Out of scope (thin-wrapper boundary): GCP service-account impersonation, a
machine-readable capabilities index.

See [CHANGELOG.md](CHANGELOG.md) for what has already landed.
