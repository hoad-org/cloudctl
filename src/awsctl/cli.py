"""
awsctl.cli — main entry point and command dispatcher.

The real binary installed by Poetry is 'awsctl' → awsctl.cli:main.

Shell wrapper contract
----------------------
The bash/zsh/fish wrapper calls:
    command awsctl --eval <subcommand> [args] > $tmp
    source $tmp

For env-mutating commands (switch, logout, login --account/--role/--region)
the binary must emit 'export K=V' / 'unset K' lines to stdout.
All user-facing output goes to stderr (BaseCommand.console is stderr=True).

The --check-strategy flag lets the shell wrapper ask "does this command
need EVAL?" before it decides whether to capture or stream stdout.
"""

import importlib.metadata
import sys
from pathlib import Path
from typing import Any, List, Optional


from . import core, utils
from .context_manager import load_context

# Patchable console references (tests monkeypatch these)
console = utils.console
stdout_console = utils.stdout_console

CONTEXT_FILE = Path.home() / ".awsctl" / "context.json"


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------


def _resolved_version() -> str:
    try:
        return importlib.metadata.version("awsctl")
    except Exception:
        return "1.2.3"


# ---------------------------------------------------------------------------
# Routing strategy
# ---------------------------------------------------------------------------


def determine_strategy(argv: List[str]) -> str:
    """
    Return "EVAL" if the shell wrapper must capture stdout and source it,
    or "EXEC" if it should just stream stdout to the terminal.
    """
    if not argv:
        return "EXEC"
    eval_cmds = {"switch", "use", "logout"}
    if argv[0] in eval_cmds:
        return "EVAL"
    if argv[0] == "login" and any(
        x in argv for x in ["--account", "-a", "--role", "-r", "--region", "-R"]
    ):
        return "EVAL"
    return "EXEC"


# ---------------------------------------------------------------------------
# Org / account helpers (patchable by tests)
# ---------------------------------------------------------------------------


def _get_org_ref(org_name: str) -> Any:
    from .sso_cache import OrgRef
    from .config import get_org

    try:
        org = get_org(org_name)
        return OrgRef(
            org.get("name", ""),
            org.get("sso_start_url", ""),
            org.get("sso_region", ""),
        )
    except Exception:
        return None


def _resolve_account_id(org_ref: Any, target: Optional[str]) -> Optional[str]:
    if target:
        return target
    return None


# ---------------------------------------------------------------------------
# Command handlers (one per subcommand; each returns int exit code)
# ---------------------------------------------------------------------------


def cmd_login(args: Any) -> int:
    org_name = getattr(args, "org", None)
    if not org_name:
        # Try to infer from context
        ctx = load_context()
        org_name = ctx.get("current_org") if ctx else None
    if not org_name:
        # Try from config if only one org is present
        cfg = core.load_orgs_config()
        orgs = cfg.get("orgs", []) if isinstance(cfg, dict) else cfg
        if len(orgs) == 1:
            org_name = orgs[0].get("name")
    if not org_name:
        console.print(
            "[red]No org specified. Use 'awsctl login <org>' or configure a default.[/]\n"
            "Run [bold]awsctl accounts[/bold] to determine which org to use."
        )
        return 1
    force = getattr(args, "force", False)
    return core.cmd_login(org_name, force=force)


def cmd_switch(args: Any) -> int:
    from .commands.switch import SwitchCommand

    return SwitchCommand().execute(args)


def cmd_logout(args: Any) -> int:
    """Emits unset lines to stdout (captured by shell wrapper) then clears context."""
    output = core.cmd_logout_str()
    sys.stdout.write(output + "\n")
    return 0


def cmd_exec(args: Any) -> int:
    ctx = load_context()
    account = getattr(args, "account", None) or (ctx.get("account") if ctx else None)
    role = getattr(args, "role", None) or (ctx.get("role") if ctx else None)
    region = getattr(args, "region", None) or (ctx.get("region") if ctx else None)
    command = getattr(args, "command", None) or getattr(args, "cmd", None) or []

    if not account or not role:
        console.print("[red]No active context. Run 'awsctl switch' first.[/]")
        return 1

    return core.cmd_exec(account, role, region or "", command)


def cmd_status(args: Any) -> int:
    from .context_manager import print_status

    print_status()
    return 0


def cmd_accounts(args: Any) -> int:
    from .commands.accounts import AccountsCommand

    return AccountsCommand().execute(args)


def cmd_doctor(args: Any) -> int:
    from . import doctor

    return doctor.run_diagnostics(fix_path=getattr(args, "fix_path", False))


def cmd_init(args: Any) -> int:
    from .commands.init import InitCommand

    return InitCommand().execute(args)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser():
    import argparse

    p = argparse.ArgumentParser(
        prog="awsctl",
        description="Enterprise Cloud Identity & Context Manager",
    )
    p.add_argument("--version", action="store_true", help="Print version and exit")
    p.add_argument("--eval", action="store_true", help="Shell wrapper mode (internal)")
    p.add_argument(
        "--check-strategy",
        metavar="CMD",
        help="Print EVAL or EXEC for CMD and exit",
    )

    sub = p.add_subparsers(dest="command")

    # login
    lp = sub.add_parser("login", help="Authenticate with a cloud provider")
    lp.add_argument("org", nargs="?", help="Organization name")
    lp.add_argument("--force", action="store_true", help="Force re-authentication")
    lp.add_argument("--account", "-a", help="Account ID (triggers EVAL mode)")
    lp.add_argument("--role", "-r", help="Role name (triggers EVAL mode)")
    lp.add_argument("--region", "-R", help="Region (triggers EVAL mode)")

    # switch / use (alias)
    for name in ("switch", "use"):
        sp = sub.add_parser(name, help="Switch cloud context interactively")
        sp.add_argument("org", nargs="?", help="Organization name")
        sp.add_argument("--account", help="Account ID")
        sp.add_argument("--role", help="Role name")
        sp.add_argument("--region", help="Region")

    # logout
    sub.add_parser("logout", help="Log out and clear context")

    # exec
    ep = sub.add_parser("exec", help="Run a command in the active context")
    ep.add_argument("command", nargs="+", metavar="CMD")

    # status
    sub.add_parser("status", help="Show active context")

    # accounts
    ap = sub.add_parser("accounts", help="List accessible accounts")
    ap.add_argument("org", help="Organization name")
    ap.add_argument("--sync", action="store_true")

    # doctor
    dp = sub.add_parser("doctor", help="Validate system configuration")
    dp.add_argument("--fix-path", action="store_true")

    # init
    sub.add_parser("init", help="Initialize configuration wizard")

    return p


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

_DISPATCH = {
    "login": "cmd_login",
    "switch": "cmd_switch",
    "use": "cmd_switch",
    "logout": "cmd_logout",
    "exec": "cmd_exec",
    "status": "cmd_status",
    "accounts": "cmd_accounts",
    "doctor": "cmd_doctor",
    "init": "cmd_init",
}


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # Fast paths that don't need full argparse
    if "--version" in argv:
        stdout_console.print(_resolved_version())
        return 0

    if "--check-strategy" in argv:
        idx = argv.index("--check-strategy")
        cmd_arg = argv[idx + 1] if idx + 1 < len(argv) else ""
        sys.stdout.write(determine_strategy([cmd_arg]) + "\n")
        return 0

    if "--help" in argv or "-h" in argv:
        stdout_console.print(
            "[bold]awsctl[/bold] — Enterprise Cloud Identity & Context Manager\n\n"
            "Commands: login, switch, logout, exec, status, accounts, doctor, init\n"
            "Options:  --version, --help, --check-strategy <cmd>"
        )
        return 0

    # Strip internal --eval flag before parsing (shell wrapper adds it)
    argv = [a for a in argv if a != "--eval"]

    parser = _build_parser()

    if not argv:
        parser.print_help(sys.stderr)
        return 0

    args = parser.parse_args(argv)
    handler_name = _DISPATCH.get(args.command)
    if handler_name is None:
        parser.print_help(sys.stderr)
        return 0

    # Look up the handler by name at call time so monkeypatching works.
    import awsctl.cli as _self

    handler = getattr(_self, handler_name)
    return handler(args)
