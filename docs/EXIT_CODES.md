# cloudctl Exit Codes

`cloudctl` uses a small, documented exit-code scheme so agents can branch on
`$?` without parsing prose. The canonical definitions live in
`src/cloudctl/exit_codes.py`, and the `errors.CloudCtlError` subclasses in
`src/cloudctl/errors.py` carry matching `exit_code` attributes.

> **Honest status:** the scheme is defined and applied at the obvious sites, but
> not every failure path emits a specific code yet. When a failure is genuinely
> uncategorised, `ERROR` (1) is the correct answer.

## Exit code table

| Code | Name | Meaning | Agent action |
|------|------|---------|--------------|
| **0** | `OK` | Success | Continue |
| **1** | `ERROR` | General / uncategorised failure | Stop, read stderr |
| **2** | `AUTH` | Authentication required (no/expired SSO session) | Run `cloudctl login <org>`, retry |
| **3** | `NOT_FOUND` | Invalid org / account / role | Verify names via `accounts` / `list-roles` |
| **4** | `DENIED` | Permission / role access denied (guardrails) | Request access; do not blindly retry |
| **5** | `USAGE` | Invalid arguments / cannot prompt in non-TTY | Fix arguments |

## Notes per code

### 0 — OK
Command succeeded. Proceed to the next step.

### 1 — ERROR
Unrecognised command, unexpected exception, or an error with no more specific
category. Read stderr; do not assume it is retryable.

### 2 — AUTH
No active SSO session, or the token expired. Re-authenticate:

```bash
cloudctl login myorg
```

Then retry the original command.

### 3 — NOT_FOUND
The org, account, or role does not exist / is not visible to you.

```bash
cloudctl accounts myorg --format json
cloudctl list-roles myorg --account 123456789012 --format json
```

### 4 — DENIED
Guardrails or the provider denied access to the requested role. This is a
policy decision, not a transient error — correct the target or request access.

### 5 — USAGE
Invalid arguments, or a non-interactive context where the tool would otherwise
need to prompt (e.g. `switch --non-interactive` without `--account/--role/--region`).

## Agent workflow example

```bash
#!/usr/bin/env bash
set -euo pipefail

cloudctl login myorg
rc=$?
if [ "$rc" -eq 2 ]; then
  echo "auth required — manual login needed" >&2
  exit 2
fi

cloudctl exec --org myorg --account 123456789012 --role AdministratorAccess \
  --region eu-west-2 -- terraform plan
case "$?" in
  0) echo "ok" ;;
  2) echo "re-auth needed" >&2; exit 2 ;;
  3) echo "check org/account/role" >&2; exit 3 ;;
  4) echo "access denied" >&2; exit 4 ;;
  *) echo "failed" >&2; exit 1 ;;
esac
```

## References

- `src/cloudctl/exit_codes.py` — canonical code definitions
- `src/cloudctl/errors.py` — error classes carrying `exit_code`
- [Error Reference](ERROR_REFERENCE.md) — error messages and remedies
