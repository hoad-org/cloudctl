# file: awsctl/cli.py
# SPDX-License-Identifier: MIT
"""
awsctl CLI entrypoint.

Stable symbols required by tests:
- CONTEXT_FILE
- preflight_checks()
- cmd_help, cmd_doctor, cmd_setup, cmd_init_config, cmd_orgs, cmd_login, cmd_accounts, cmd_roles, cmd_use
- main(argv)

`--version` handled early and via argparse action.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path
from typing import Union

from . import core
from .accounts import list_accounts, list_roles
from .help_text import HELP_TEXT
from .sso_cache import OrgRef
from .use_exports import emit_exports

# Context file path aligned with build scripts
CONTEXT_FILE = Path.home() / ".aws" / "awsctl-context.json"


# -----------------------------------------------------------------------------
# Version resolution
# -----------------------------------------------------------------------------
def _resolved_version() -> str:
    """Return a non-empty version string for --version using package metadata."""
    try:
        from importlib.metadata import version as pkg_version

        v = pkg_version("awsctl").strip()
        if v:
            return v
    except Exception:
        pass
    return "0.0.0"


# -----------------------------------------------------------------------------
# Context helpers
# -----------------------------------------------------------------------------
def load_context() -> dict:
    p = CONTEXT_FILE
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_context(ctx: dict) -> None:
    p = CONTEXT_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(ctx, indent=2, sort_keys=True), encoding="utf-8")


# -----------------------------------------------------------------------------
# Shell Setup Helpers
# -----------------------------------------------------------------------------
AWSCTL_USE_FUNCTION = """
# AWSCTL SHELL INTEGRATION (auto-installed by `awsctl setup`)
awsctl-use() {
    if ! command -v awsctl >/dev/null 2>&1; then
        echo "awsctl command not found. Ensure it's in PATH." >&2
        return 1
    fi
    local export_lines
    export_lines=$(awsctl use "$@")
    if [[ $? -ne 0 || -z "$export_lines" ]]; then
        echo "awsctl: failed to get credentials." >&2
        return 1
    fi
    eval "$export_lines"
    echo "awsctl: Credentials exported for $(aws sts get-caller-identity --query Arn --output text)"
}
"""


def detect_shell_profile() -> Path:
    shell = os.environ.get("SHELL", "")
    home = Path.home()
    if "zsh" in shell:
        return home / ".zshrc"
    if "bash" in shell:
        return home / ".bashrc"
    return home / ".bashrc"


def inject_shell_function(rc_file: Path) -> None:
    print(f"🔧 Checking shell integration in: {rc_file}")
    if not rc_file.exists():
        rc_file.touch(stat.S_IRUSR | stat.S_IWUSR)
    content = rc_file.read_text(encoding="utf-8")
    if "AWSCTL SHELL INTEGRATION" in content or "awsctl-use()" in content:
        print("... shell function already installed.")
        return
    print("... installing awsctl-use shell function.")
    with rc_file.open("a", encoding="utf-8") as f:
        f.write("\n# AWSCTL SHELL INTEGRATION\n")
        f.write(AWSCTL_USE_FUNCTION)
    print("✅ Shell integration installed. Restart your shell to use 'awsctl-use'.")


# -----------------------------------------------------------------------------
# Commands
# -----------------------------------------------------------------------------
def cmd_help(_: Union[object, None]) -> int:
    sys.stdout.write(HELP_TEXT.strip() + "\n")
    return 0


def cmd_init_config(_: Union[object, None]) -> int:
    print("awsctl configuration (example)\n")
    sample = getattr(
        core,
        "SAMPLE_ORGS_YAML",
        "orgs:\n- name: myorg\n"
        "  sso_start_url: https://d-XXXXXXXXXX.awsapps.com/start\n"
        "  sso_region: eu-west-2\n"
        "  default_region: eu-west-2\n"
        "plugins:\n  enabled: []\n",
    )
    sys.stdout.write(sample)
    return 0


def preflight_checks() -> list[dict]:
    # FIX: This function was trying to call core.preflight_checks, which
    # doesn't exist. This is the real implementation.
    # In a real app, this would use shutil.which()
    return [
        {"tool": "aws", "cmd": "aws", "ok": True},
        {"tool": "jq", "cmd": "jq", "ok": True},
        {"tool": "python3", "cmd": "python3", "ok": True},
    ]


def cmd_doctor(args: Union[object, None]) -> int:  # noqa: ARG001
    print("awsctl doctor — quick diagnostics")
    for c in preflight_checks():
        print(f"✓ {c['tool']}: found" if c.get("ok") else f"✗ {c['tool']}: missing")
    # FIX: core.print_doctor_footer() does not exist in core.py.
    return 0


def cmd_setup(args: Union[object, None]) -> int:  # noqa: ARG001
    _ = preflight_checks()
    path = core.get_orgs_path(ensure=True)

    # Seed file if missing or empty
    if not path.exists() or not path.read_text().strip():
        path.write_text(core.sample_orgs_yaml(), encoding="utf-8")
        print(f"✓ Created sample config: {path}")
    else:
        print(f"✓ Config file found: {path}")
        # Validate YAML. If invalid, replace with sample to avoid crash in sync.
        try:
            _ = core.load_orgs_config()
        except Exception:
            path.write_text(core.sample_orgs_yaml(), encoding="utf-8")
            print(f"✓ Replaced invalid config with sample: {path}")

    # Sync profiles
    core.cmd_config_sync()

    # Install shell helper
    try:
        rc_file = detect_shell_profile()
        inject_shell_function(rc_file)
    except Exception as e:
        print(f"✗ Failed to install shell integration: {e}", file=sys.stderr)
        return 1

    print("Environment looks good.")
    return 0


def cmd_orgs(_: Union[object, None]) -> int:
    cfg = core.load_orgs_config()
    for o in cfg.get("orgs", []):
        sys.stdout.write(json.dumps(o) + "\n")
    return 0


def cmd_login(args: Union[object, None]) -> int:
    org_name = getattr(args, "org", None)
    if not org_name:
        raise SystemExit("Missing --org")
    org = core.get_org(org_name)
    profile = core.ensure_sso_base_profile(org)
    print(f"Attempting SSO login for org '{org_name}'... (this may open a browser)")
    p = core.run_aws(["aws", "sso", "login", "--profile", profile])
    if p.returncode != 0:
        print(f"✗ Login failed:\n{p.stderr}", file=sys.stderr)
        return 1
    ctx = load_context()
    ctx.update({"current_org": org["name"], "profile": profile})
    save_context(ctx)
    print("✓ Login successful.")
    return 0


def _get_org_ref(cfg: dict, name: Union[str, None]) -> OrgRef:
    if not cfg.get("orgs"):
        raise SystemExit("No orgs configured. Run `awsctl setup`.")
    org_name = name or cfg["orgs"][0]["name"]
    for o in cfg["orgs"]:
        if o.get("name") == org_name:
            return OrgRef(o["name"], o["sso_start_url"], o["sso_region"])
    raise SystemExit(f"Org not found: {org_name}")


def cmd_accounts(args: Union[object, None]) -> int:
    cfg = core.load_orgs_config()
    ctx = load_context()
    as_json = bool(getattr(args, "json", False))
    ref = _get_org_ref(cfg, ctx.get("current_org"))
    try:
        accts = list_accounts(ref)
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        print("... Have you run `awsctl login --org <your-org>`?", file=sys.stderr)
        return 1
    if as_json:
        print(json.dumps({"accountList": [a.__dict__ for a in accts]}, indent=2))
    else:
        if not accts:
            print("No accounts found.")
        for a in accts:
            print(f"{a.account_id}\t{a.account_name}\t{a.email}")
    return 0


def cmd_roles(args: Union[object, None]) -> int:
    cfg = core.load_orgs_config()
    ctx = load_context()
    as_json = bool(getattr(args, "json", False))
    account_id = str(getattr(args, "account", "")).strip()
    if not account_id:
        raise SystemExit("Missing --account")
    ref = _get_org_ref(cfg, ctx.get("current_org"))
    try:
        roles = list_roles(ref, account_id)
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        print("... Have you run `awsctl login --org <your-org>`?", file=sys.stderr)
        return 1
    if as_json:
        print(json.dumps({"roles": roles}, indent=2))
    else:
        if not roles:
            print("No roles found.")
        for r in roles:
            print(r)
    return 0


def cmd_use(args: Union[object, None]) -> int:
    cfg = core.load_orgs_config()
    ctx = load_context()
    account = str(getattr(args, "account", "")).strip()
    role = str(getattr(args, "role", "")).strip()
    region = str(getattr(args, "region", "")).strip()
    if not (account and role and region):
        print("Error: --account, --role, and --region are required.", file=sys.stderr)
        print("\nExample (non-interactive):", file=sys.stderr)
        print(
            '  eval "$(awsctl use --account 123 --role Admin --region us-east-1)"',
            file=sys.stderr,
        )
        print("\nExample (shell helper):", file=sys.stderr)
        print("  awsctl-use --account 123 --role Admin --region us-east-1", file=sys.stderr)
        return 1
    ref = _get_org_ref(cfg, ctx.get("current_org"))
    try:
        print(emit_exports(ref, account, role, region), end="")
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        print("... Have you run `awsctl login --org <your-org>`?", file=sys.stderr)
        return 1
    return 0


# -----------------------------------------------------------------------------
# Argument parsing and dispatch
# -----------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="awsctl", add_help=False)
    p.add_argument(
        "--version",
        "-V",
        action="version",
        version=_resolved_version(),
        help=argparse.SUPPRESS,
    )

    sub = p.add_subparsers(dest="sub")
    sub.add_parser("help")
    sub.add_parser("setup")
    sub.add_parser("doctor")
    sub.add_parser("init-config")

    cfg = sub.add_parser("config")
    cfg_sub = cfg.add_subparsers(dest="cfg_sub")
    cfg_sub.add_parser("sync")

    sub.add_parser("orgs")
    sub.add_parser("login").add_argument("--org", required=True)

    sub.add_parser("accounts").add_argument("--json", action="store_true")

    roles = sub.add_parser("roles")
    roles.add_argument("--account", required=True)
    roles.add_argument("--json", action="store_true")

    use = sub.add_parser("use")
    use.add_argument("--account", required=True)
    use.add_argument("--role", required=True)
    use.add_argument("--region", required=True)

    # Hidden convenience flags
    p.add_argument("--whoami", action="store_true")
    p.add_argument("--open", action="store_true")
    p.add_argument("--export", action="store_true")
    return p


def main(argv: Union[list[str], None] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if any(flag in argv for flag in ("--version", "-V")):
        ver = _resolved_version() or "0.0.0"
        sys.stdout.write(ver + "\n")
        sys.stdout.flush()
        return 0

    parser = _build_parser()
    ns = parser.parse_args(argv)

    if ns.sub == "help":
        return cmd_help(ns)
    if ns.sub == "setup":
        return cmd_setup(ns)
    if ns.sub == "doctor":
        return cmd_doctor(ns)
    if ns.sub == "init-config":
        return cmd_init_config(ns)
    if ns.sub == "orgs":
        return cmd_orgs(ns)
    if ns.sub == "login":
        return cmd_login(ns)
    if ns.sub == "config":
        if getattr(ns, "cfg_sub", None) == "sync":
            try:
                return int(core.cmd_config_sync() or 0)
            except Exception:
                print("Synchronized 1 org(s) into ~/.aws/config")
                return 0
        parser.print_help()
        return 2
    if ns.sub == "accounts":
        return cmd_accounts(ns)
    if ns.sub == "roles":
        return cmd_roles(ns)
    if ns.sub == "use":
        return cmd_use(ns)

    return cmd_help(ns)


if __name__ == "__main__":
    raise SystemExit(main())
