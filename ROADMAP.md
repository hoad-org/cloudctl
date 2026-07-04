# cloudctl Roadmap

**Current version:** `1.0.0b0` (beta). This is the honest remaining backlog for
the agent-first overhaul — no enterprise/compliance items, only real work.

## Now

- **Collapse the verb set.** `login`/`switch`/`use`/`exec` and
  `status`/`env`/`whoami` overlap (`use` == `switch`). Reduce to a minimal,
  orthogonal command set with `exec` as the canonical stateless form.
- **Finish the output contract.** Extend `--format json` to `whoami` and `exec`
  (currently `exec` only has `--json-errors`). Route human/console output to
  stderr where it currently goes to stdout, so JSON on stdout stays clean.
- **Emit exit codes everywhere.** The `OK/ERROR/AUTH/NOT_FOUND/DENIED/USAGE`
  scheme is defined but only partially applied; wire the specific codes at every
  unambiguous failure site.

## Next

- **Remove `wizard/`.** ~863 LOC tied to `init`; entangled with critical paths.
  Cut it carefully, backed by behavioural tests.
- **Behavioural test coverage for credential injection** across all three
  providers, so the "green suite while broken" failure mode can't recur.
- **Consolidate the two `exec` paths** (`cli.cmd_exec → commands/exec.py` vs
  `core.py::cmd_exec` + `use_exports`) so there is one live path.

## Later

- **Portable, non-interactive `switch`** that doesn't depend on the shell-wrapper
  to apply exports (agents already use `exec`; make the human path robust too).
- **1.0.0 (non-beta)** once the credential spine, output contract, and exit codes
  are proven against real invocations.

See [CHANGELOG.md](CHANGELOG.md) for what has already landed.
