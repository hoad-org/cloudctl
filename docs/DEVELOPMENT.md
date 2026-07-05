# cloudctl Development Guide

For working on `cloudctl` itself. See also [CLAUDE.md](../CLAUDE.md) for the
authoritative developer notes.

## Setup

```bash
git clone https://github.com/hoad-org/cloudctl.git
cd cloudctl
python3.12 -m pip install -e ".[dev]"
cloudctl --version
```

## Repository layout

```
src/cloudctl/
  cli.py             # arg parser (_build_parser) + dispatch (_DISPATCH) + handlers
  core.py            # login/exec/logout core logic
  context_manager.py # active-context persistence (current_context.json)
  use_exports.py     # AWS export-line generation (switch/eval path)
  exit_codes.py      # OK/ERROR/AUTH/NOT_FOUND/DENIED/USAGE
  errors.py          # CloudCtlError subclasses (carry exit_code)
  role_validator.py  # role existence check + fuzzy suggestions
  providers/         # aws.py, gcp.py, azure.py, base.py — get_credentials contract
  commands/          # per-command executors (exec, accounts, init, org, ...)
  guardrails.py      # allowed-roles / break-glass / audit (no-hang under non-TTY)
  config.py          # orgs.yaml load/save
tests/               # pytest suite
docs/                # this documentation
```

Two things to keep in mind:

- The **live** `exec` path is `cli.cmd_exec → commands/exec.py::ExecCommand →
  providers/aws.py::get_credentials`. `core.py::cmd_exec` + `use_exports` is a
  parallel path used by the switch/eval flow and some tests.
- The parser is authoritative in `cli.py::_build_parser`. The
  `configure_parser()` methods inside `commands/*.py` are **not** wired in.

## Tests

```bash
python -m pytest -q                 # full suite
python -m pytest --cov=src/cloudctl # with coverage
```

A green suite is necessary but **not** sufficient — historically the tests passed
while credential injection was broken. When fixing a bug, add a **behavioural**
test (see `tests/test_providers.py::TestAwsProviderCredentials`) and verify
against a real `cloudctl` invocation. Do not hardcode a test count in docs.

## Code style

- **black** (formatting), **ruff** (lint), **mypy** (types).

```bash
black src/ tests/
ruff check --fix src/ tests/
mypy src/cloudctl
```

## Golden rules when changing the tool

1. **Never hang.** Any interactive prompt must gate on the non-interactive check
   (`cli._non_interactive`) and fail fast with an actionable message.
2. **Never set `AWS_PROFILE`** or write static profiles. Inject env only.
3. **SSO portal calls use `org.sso_region`**; command execution uses the user's
   `--region`. Don't conflate them.
4. **Verify against reality**, not just tests.

## Adding a command

1. Add the subparser and arguments in `cli.py::_build_parser`.
2. Register the handler in `_DISPATCH`.
3. Implement the handler (in `cli.py` or a `commands/*.py` executor).
4. Add behavioural tests.
5. Update the relevant docs and `CHANGELOG.md`.

## Version

Version lives in `src/cloudctl/_version.py` and `pyproject.toml`. Current:
`1.0.0b0` (beta). Uses semantic versioning.

## Resources

- [CHANGELOG.md](../CHANGELOG.md)
- [ROADMAP.md](../ROADMAP.md)
- [CLAUDE.md](../CLAUDE.md) — repo conventions
