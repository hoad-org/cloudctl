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
- **Zero-disk `--no-cache` mode.** `run --no-cache` authenticates in memory and
  vends creds without cloudctl ever writing the SSO token.

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

- **Portable, non-interactive `switch`** that doesn't depend on the shell-wrapper
  to apply exports (agents already use `run`; make the human path robust too).
- **1.0.0 (non-beta)** once the credential spine, output contract, and exit codes
  are proven against real invocations.

## Major evolution — dual-audience identity broker

Design and rationale: **[ADR 0001](docs/adr/0001-agentic-identity-broker.md)**.
Turns cloudctl into a control plane serving humans (browser SSO) *and* agents
(headless OIDC), as one core behind a CLI + an MCP server. Each phase is
independently shippable; we come back to this when ready.

- **Phase 1 — core/adapters + `cloudctl mcp`.** One `cloudctl-core`; thin CLI;
  ship a stdio MCP server so agents stop scraping `--help`.
- **Phase 2 — OIDC workload-identity federation.** Pluggable `CredentialSource`;
  headless agent auth (GitHub Actions / K8s SA / SPIFFE) — no browser, no secret.
- **Phase 3 — downscoping + deny-by-default policy.** Session policies / scoped
  impersonation at mint time → real least-privilege.
- **Phase 4 (gated) — remote broker `cloudctld`.** Server-side policy, central
  tamper-proof audit, instant revoke = real *control*, not just hygiene. Gated on
  genuinely running multiple clouds × orgs × a fleet of agents.

**Boundary held:** cloudctl mints/gates/audits identity; it never *executes*
cloud operations (that's the provider MCPs / native CLIs). If the Phase-4 gate
isn't met, stop at Phase 3 and use provider MCPs + native federation.

See [CHANGELOG.md](CHANGELOG.md) for what has already landed.
