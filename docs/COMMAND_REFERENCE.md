# cloudctl Command Reference

All commands are invoked as `cloudctl <command>`. The full command set (from
`cloudctl --help`): `login`, `switch`, `use`, `logout`, `cache-clear`, `exec`,
`status`, `env`, `accounts`, `doctor`, `init`, `prompt`, `upgrade`, `org`,
`list`, `uninstall`, `completion`, `list-roles`, `setup`, `whoami`, `open`,
`orgs`.

> Some verbs overlap (`login`/`switch`/`use`/`exec`, `status`/`env`/`whoami`).
> `exec` is the canonical, stateless form for automation.

## Core commands

### `login <org>`

Authenticate an org's SSO session (opens a browser) and record it as the active
context.

```bash
cloudctl login myorg
```

### `exec` — the canonical agent form

Run a command with credentials injected. Stateless: takes everything on the
command line, needs no prior context. **Requires a literal `--`** before the
child command.

```bash
cloudctl exec --org <ORG> --account <ID> --role <ROLE> --region <REGION> -- <command...>
```

Options: `--org`, `--account`, `--role`, `--region`, `--json-errors` (emit
errors as JSON).

```bash
cloudctl exec --org myorg --account 123456789012 --role ReadOnly \
  --region eu-west-2 -- aws s3 ls

cloudctl exec --org myorg --account 123456789012 --role AdministratorAccess \
  --region eu-west-2 -- terraform plan
```

Notes:
- `--region` is the region the **child** runs in (injected as
  `AWS_REGION`/`AWS_DEFAULT_REGION`). The SSO portal call uses the org's
  `sso_region`.
- No `AWS_PROFILE` is ever set.

### `switch <org>` / `use <org>`

Set a persistent context. `use` is an alias for `switch`. Emits export lines via
the shell wrapper.

```bash
cloudctl switch myorg --account 123456789012 --role ReadOnly \
  --region eu-west-2 --non-interactive
```

In a non-TTY / CI context, `switch` will **not** prompt — it fails fast asking
for explicit `--account/--role/--region`.

### `logout`

Clear the active context and provider session.

```bash
cloudctl logout
```

### `cache-clear`

Clear cached SSO tokens / account data.

## Discovery commands

### `accounts <org>`

List accessible accounts. Supports `--format json`, `--sync` (refresh from
provider).

```bash
cloudctl accounts myorg --format json
```

### `list-roles <org> [--account <id>]`

List IAM roles you can assume. Supports `--format json`.

```bash
cloudctl list-roles myorg --account 123456789012 --format json
```

### `orgs` / `org list`

List configured orgs.

## Context / identity

### `status` / `env`

Show the active context. Both support `--format json`.

```bash
cloudctl status --format json
```

### `whoami`

Show the active identity. Supports `--format json`.

## Setup / maintenance

### `init` / `setup`

Create (`init`) or merge sample defaults into (`setup`) `orgs.yaml`.

### `doctor`

Diagnose the install and config.

```bash
cloudctl doctor
```

### `open`

Open the cloud provider console in a browser.

### `upgrade`, `uninstall`, `completion`, `prompt`, `list`

Maintenance / helper commands (`completion` emits shell completion; `prompt`
prints an agent-oriented usage prompt).

## Exit codes

See [Exit Codes](EXIT_CODES.md). Summary: `0` OK, `1` ERROR, `2` AUTH,
`3` NOT_FOUND, `4` DENIED, `5` USAGE.

## Next steps

- [Quick Start](QUICK_START.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Error Reference](ERROR_REFERENCE.md)
