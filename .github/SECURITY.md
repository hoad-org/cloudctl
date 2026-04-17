# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 3.x (latest) | ✅ Active security fixes |
| 2.x | ❌ End of life — upgrade to v3 |
| < 2.0 | ❌ End of life |

## Reporting a Vulnerability

**DO NOT open a public GitHub issue for security vulnerabilities.**

Email **`craighoad+security@hotmail.com`** with:
- A description of the vulnerability
- Steps to reproduce (proof-of-concept if available)
- Affected versions
- Suggested fix (optional)

We will acknowledge receipt within **1 business day** and aim to provide an assessment within **5 business days**.

## Disclosure Policy

- We follow **coordinated disclosure**: please allow up to 90 days for a patch before public disclosure.
- Once a fix is released we will publish a GitHub security advisory and credit the reporter unless anonymity is requested.

## Security Controls

| Control | Implementation |
|---------|---------------|
| **Ephemeral credentials** | STS tokens exist only in the active shell session; nothing written to disk |
| **Shell injection protection** | All exported variables sanitised with `shlex.quote()` before shell evaluation |
| **TTY Guard** | `--eval` mode warns when used outside the validated shell wrapper context |
| **Registry integrity** | org registry verified with Minisign signature before use |
| **Audit logging** | Break-glass role access logged to `~/.awsctl/audit.log` (mode 0600) |
| **Atomic file writes** | Config and profile writes use `mkstemp` + `os.replace()` to prevent partial updates |
| **Dependency scanning** | `pip-audit` runs on every push (CI) and twice weekly (scheduled audit) |
| **Secret scanning** | Gitleaks runs on every push and pull request |
| **SAST** | Bandit runs on every push |

## Security Update SLAs

| Severity | CVSS | Target patch time |
|----------|------|-------------------|
| Critical | ≥ 9.0 | 48 hours |
| High | 7.0–8.9 | 7 days |
| Medium / Low | < 7.0 | Next regular release |
