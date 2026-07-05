# ADR 0001 — cloudctl as a dual-audience cloud identity broker

- **Status:** Proposed
- **Date:** 2026-07-05
- **Deciders:** Craig
- **Supersedes:** the implicit "CLI wrapper" positioning

## Context

cloudctl is a multicloud (AWS/GCP/Azure) SSO wrapper. Its zero-trust core is
verified (no profiles written, STS creds env-only, `--no-cache` = zero creds on
disk). Two facts shape the next act:

1. **Mixed audience.** Humans use it interactively (browser SSO); agents use it
   headless. Neither can be dropped.
2. **It must add real security, not theatre**, and must not become a redundant
   middleman to cloud providers' own MCP servers.

## Decision drivers

- Serve humans *and* agents first-class from one codebase.
- Multi-cloud × multi-org **uniformity** is the core value; a leaky abstraction
  destroys it.
- Add security that survives scrutiny; never sell hygiene as control.
- Ride cloud primitives (STS, WIF, session policies); never reinvent them.

## Decisions

### D1 — Ports & adapters: one core, two thin adapters

`cloudctl-core` holds all logic (credential sources, providers, policy, context,
injection, audit). Two adapters call it:

- **CLI** — `run -- cmd` (subprocess injection; humans, shells, CI).
- **MCP** — `cloudctl mcp` starts a stdio MCP server; tool handlers call the same
  core and return **data**, not shell side-effects.

One package, one install, two modes. The MCP is not a second product.

### D2 — Pluggable `CredentialSource` (dual auth, auto-detected)

Auth method is orthogonal to context/injection/policy/audit.

```python
class CredentialSource(Protocol):
    def available(self, ctx) -> bool:            # usable in this environment?
    def authenticate(self, target) -> Session:   # short-lived session, in-memory

@dataclass
class Session:
    credentials: dict[str, str]   # env vars to inject
    identity: dict | None         # live-verified principal
    expires_at: str | None
    persist: bool = False         # honour --no-cache
```

Implementations, resolved in priority order:

1. **OidcFederationSource** — agents/CI. Present an OIDC token (GitHub Actions,
   GitLab, K8s SA, SPIFFE) → `AssumeRoleWithWebIdentity` / GCP WIF / Azure
   federated creds. No browser, no stored secret.
2. **BrowserSsoSource** — humans. The existing device flow.
3. **AmbientSource** — fallback to an existing login.

Auto-detect: OIDC token in env → federate; else TTY+browser → device flow; else
ambient. **Same command, right auth for the caller.**

### D3 — Positioning: control plane, never data plane

cloudctl **mints, gates, and audits identity**. It **never executes cloud
operations** — that is the provider MCPs' / native CLIs' job. Held ruthlessly,
this is a boundary provider MCPs do not occupy. Lost, cloudctl is a redundant
hop.

### D4 — Local vs remote is a *staged* decision, not a fork to guess now

| | Local tool (CLI/MCP on the agent box) | Remote broker service |
|---|---|---|
| Gives | credential hygiene + least-privilege downscoping + audit-of-intent | real control: server-side policy, no standing agent identity, instant revoke, tamper-proof audit |
| Trust boundary | soft (compromised agent has what it holds) | hard |
| Cost | low | a service to run/secure/keep-HA |

Start local. Graduate to remote **only when the gate is met** (below). Selling
the local tool as a control plane is theatre.

## MCP tool surface (data-shaped, deny-by-default)

- `list_targets()` → `[{cloud, org, account|project|subscription, role, allowed}]`
- `session_status(target)` → `{identity, expires_at, valid}`
- `get_scoped_credentials(target, scope?)` → short-lived, **downscoped** env creds
  (hand off to a provider MCP/SDK)
- `exec(target, argv, scope?)` → `{stdout, stderr, exit}` (convenience)
- `request_access(target, reason)` → gated grant (Phase 4)

## Phased build plan

Each phase is independently shippable and valuable.

- **Phase 0 — done.** Honest zero-trust wrapper; verified; `--no-cache`.
- **Phase 1 — Core/adapters + `cloudctl mcp`.** Refactor logic into
  `cloudctl-core`; make the CLI a thin adapter; ship the MCP mode
  (BrowserSso + Ambient sources). *Low risk, highest leverage for agents.*
- **Phase 2 — OIDC workload-identity federation.** `OidcFederationSource`.
  Headless auth, no browser — the "truly agentic" unlock. Ride native WIF; do
  not reinvent.
- **Phase 3 — Downscoping + deny-by-default policy.** Attach session policies /
  scoped impersonation at mint time so vended creds are already least-privilege;
  signed local policy, deny-by-default. *The real local security win.*
- **Phase 4 — Remote broker (`cloudctld`), gated.** Agents authenticate to the
  service via WIF; server-side policy + minting + central tamper-proof audit +
  revoke. CLI/MCP become clients. *The real control plane.*

### Phase 4 gate (all must hold)

≥2 clouds **and** several orgs **and** a fleet of agents **and** a team needing
central governance / revocation / audit. If not met, **stop at Phase 3** and use
provider MCPs + native federation for the rest.

## Consequences

**Positive**
- Humans (CLI) and agents (MCP) both first-class from one core.
- Provable least-privilege at Phase 3; real control at Phase 4.
- Clear, defensible boundary vs provider MCPs.

**Negative / risks**
- Two adapters = maintenance tax → keep them thin, test the core.
- Dual auth broadens attack surface; WIF audience/subject misconfig is a real
  breach vector → strict defaults, the weakest path defines security.
- Phase 4 is a service — a buggy credential broker is a breach, not a papercut.
  Build to a real standard or not at all.

## Alternatives considered

- **Provider MCPs + native federation only.** Correct for single-cloud; loses
  cross-cloud uniform policy/audit. Rejected only for genuinely multi-everything.
- **MCP-only (drop the CLI).** Rejected — humans, shells, and CI need the CLI.
- **Local-only forever.** Acceptable *as hygiene* — but cannot honestly claim
  "control." Fine if the Phase 4 gate is never met.
