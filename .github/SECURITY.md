# Security Policy

## Supported Versions

`cloudctl` is a personal project. The current line is `1.0.0` beta; only the
latest version receives fixes.

| Version | Supported |
|---------|-----------|
| 1.0.x (beta, latest) | ✅ Active fixes |
| < 1.0 | ❌ Not supported |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report privately via the repository's GitHub security advisories
(`hoad-org/cloudctl` → Security → Report a vulnerability). Include:

- A description of the vulnerability
- Steps to reproduce (proof-of-concept if available)
- Affected version

Do not include real credentials in a report.

## Security posture

See [docs/SECURITY.md](../docs/SECURITY.md) for the actual credential model.
Summary:

| Control | Implementation |
|---------|---------------|
| **Short-lived credentials** | STS keys / access tokens vended on demand, injected into the child process only; never written to cloudctl's own files |
| **No `AWS_PROFILE`** | Injected keys are self-contained; no static profiles written |
| **No secrets on disk** | `orgs.yaml` (mode 0600) holds config only — no credentials |
| **No-hang guards** | Fails fast in non-TTY contexts instead of prompting |
| **Break-glass** | Sensitive-role justification read from `CLOUDCTL_BREAK_GLASS_REASON` |
| **CI checks** | ruff / mypy / pytest run in `.github/workflows/ci.yaml` |
