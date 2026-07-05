# cloudctl Error Reference

Quick lookup for common error conditions and their remedies. Exit codes map to
the scheme in [Exit Codes](EXIT_CODES.md): `0` OK, `1` ERROR, `2` AUTH,
`3` NOT_FOUND, `4` DENIED, `5` USAGE.

## Authentication (exit 2)

### No / expired SSO session

**Cause:** no active SSO token, or it expired.

**Fix:**
```bash
cloudctl login myorg
```
Then retry the original command.

### Cannot reach the SSO endpoint

**Cause:** network / proxy issue reaching the provider.

**Fix:** check connectivity and any corporate proxy, then retry.

## Configuration (exit 5)

### `orgs.yaml not found`

**Fix:**
```bash
cloudctl init
```
Then edit `~/.config/cloudctl/orgs.yaml`.

### Invalid YAML / schema

**Fix:** the top-level `orgs:` key must be a **list** of org objects (each with a
`name`), and `enabled_orgs` lists the active ones. Use 2-space indentation, not
tabs. Validate:
```bash
cloudctl doctor
```

### Unknown provider

**Cause:** an org's `provider` is not one of `aws`, `gcp`, `azure`.

**Fix:** set a valid provider in `orgs.yaml`.

## Org / account / role (exit 3)

### Organization not found

**Fix:**
```bash
cloudctl orgs
cloudctl switch myorg ...
```

### Account not found

**Fix:**
```bash
cloudctl accounts myorg --format json
```

### Role not found

**Fix:**
```bash
cloudctl list-roles myorg --account 123456789012 --format json
```
Use the exact role name (matching is case-insensitive; the tool suggests close
matches). See [Role Validation](ROLE_VALIDATION_FEATURE.md).

## Access denied (exit 4)

### Denied to the requested role

**Cause:** guardrails or the provider denied assuming the role.

**Fix:** target a role you are entitled to, or request access. For a sensitive
role in a non-interactive context, supply the justification via
`CLOUDCTL_BREAK_GLASS_REASON`.

## Usage (exit 5)

### `exec` consumed the child command's flags

**Cause:** missing the literal `--` before the child command.

**Fix:**
```bash
cloudctl exec --org myorg --account 123456789012 --role ReadOnly \
  --region eu-west-2 -- aws s3 ls
```

### `switch --non-interactive` without target

**Cause:** in a non-TTY context, `switch` cannot prompt.

**Fix:** pass `--account`, `--role`, and `--region` explicitly.

## Install (exit 1)

### `ModuleNotFoundError: No module named 'cloudctl'`

**Fix:**
```bash
python3.12 -m pip install -e .
cloudctl --version
```

### `python3.12: command not found`

**Fix:**
```bash
# macOS
brew install python@3.12
# Debian/Ubuntu
sudo apt install python3.12
```

## Next steps

- [Troubleshooting](TROUBLESHOOTING.md)
- [Command Reference](COMMAND_REFERENCE.md)
- [Quick Start](QUICK_START.md)
