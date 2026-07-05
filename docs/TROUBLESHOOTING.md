# cloudctl Troubleshooting

## Diagnosis workflow

### 1. Run the health check

```bash
cloudctl doctor
```

- All checks pass → the issue is with your operation, not the setup.
- A check fails → fix what it reports and re-run.

### 2. Check the exit code

```bash
cloudctl <command>; echo $?
```

| Code | Meaning | Action |
|------|---------|--------|
| 0 | OK | Success |
| 1 | ERROR | General failure — read stderr |
| 2 | AUTH | Re-authenticate: `cloudctl login <org>` |
| 3 | NOT_FOUND | Verify org/account/role |
| 4 | DENIED | You lack access to the role |
| 5 | USAGE | Fix arguments (or missing `--` before the child command) |

See [Exit Codes](EXIT_CODES.md).

## Common issues

### `exec` swallows the child command's flags

**Symptom:** flags like `--query` or `--output` are consumed by cloudctl.

**Cause:** missing the literal `--` separator.

```bash
# WRONG — --query is parsed by cloudctl
cloudctl exec --org myorg --account 123456789012 --role ReadOnly \
  --region eu-west-2 aws s3api list-buckets --query 'Buckets[].Name'

# CORRECT
cloudctl exec --org myorg --account 123456789012 --role ReadOnly \
  --region eu-west-2 -- aws s3api list-buckets --query 'Buckets[].Name'
```

### "session token not found" / creds work in one region but not another

**Cause (historical bug, now fixed):** conflating the SSO portal region with the
command's `--region`. The SSO `get-role-credentials` call uses the org's
`sso_region`; `--region` is injected as `AWS_REGION`/`AWS_DEFAULT_REGION` for the
child. Confirm `sso_region` is set correctly for the org in `orgs.yaml`.

### `switch` hangs or errors in CI

`switch` never prompts in a non-TTY / CI / agent context — it fails fast (exit
`5`) asking for explicit `--account/--role/--region`. Pass them, or use `exec`,
which is the wrapper-free path agents should use.

```bash
cloudctl exec --org myorg --account 123456789012 --role ReadOnly \
  --region eu-west-2 -- aws sts get-caller-identity
```

### Role name not found after listing roles

Use the exact role name from `list-roles` (matching is case-insensitive and the
tool suggests close matches, but use the canonical name):

```bash
cloudctl list-roles myorg --account 123456789012 --format json
```

### `cloudctl: command not found`

The editable install did not put `cloudctl` on your PATH, or the venv isn't
active. Re-install from the repo root and check:

```bash
python3.12 -m pip install -e .
cloudctl --version
```

### `Unable to locate credentials`

Each shell invocation is independent. Don't split `login` and the actual command
across environments and expect credentials to persist — use the stateless `exec`
form, which injects credentials into the one child process.

## Verify a working setup

```bash
cloudctl doctor
cloudctl exec --org myorg --account 123456789012 --role ReadOnly \
  --region eu-west-2 -- aws sts get-caller-identity
```

## Where state lives

| Path | Purpose |
|------|---------|
| `~/.config/cloudctl/orgs.yaml` | Org config |
| `~/.config/cloudctl/current_context.json` | Active context |
| `~/.aws/sso/cache/` | AWS SSO token cache |

If the active context looks stale, clear caches:

```bash
cloudctl cache-clear
cloudctl logout
```

## Next steps

- [Error Reference](ERROR_REFERENCE.md)
- [Command Reference](COMMAND_REFERENCE.md)
- [Configuration](CONFIGURATION.md)
