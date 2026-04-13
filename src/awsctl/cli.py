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
import os
import sys
from pathlib import Path
from typing import Any, List, Optional


from . import core, utils
from .use_exports import emit_exports  # noqa: F401 — re-exported for monkeypatch seam

# Patchable console references (tests monkeypatch these)
console = utils.console
stdout_console = utils.stdout_console

CONTEXT_FILE = Path.home() / ".awsctl" / "context.json"


def load_context():
    """
    Load context from CONTEXT_FILE with debug logging on error.
    This wrapper uses the module-level CONTEXT_FILE so tests can patch it.
    """
    import json

    if not CONTEXT_FILE.exists():
        return {}
    try:
        return json.loads(CONTEXT_FILE.read_text())
    except Exception as e:
        utils.debug_print(f"Failed to load context: {e}")
        return {}


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
    org_name = getattr(args, "org", None) or getattr(args, "org_flag", None)
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
    try:
        rc = core.cmd_login(org_name, force=force)
    except (ValueError, Exception) as e:
        utils.console.print(f"[red]Error:[/] {e}")
        return 1

    # Bridge to switch when account+role+region are provided (eval mode)
    if rc == 0 and getattr(args, "account", None) and getattr(args, "role", None):
        try:
            org_ref = _get_org_ref(org_name)
            _resolve_account_id(org_ref, getattr(args, "account", None))
        except Exception:
            pass
        import awsctl.cli as _self

        return _self.cmd_switch(args)

    return rc


def cmd_switch(args: Any) -> int:
    import awsctl.interactive as _interactive
    import awsctl.cli as _self  # for patchable emit_exports
    from .context_manager import save_context, get_previous_context
    from .config import get_org, load_config

    try:
        target = getattr(args, "target", None)

        # Handle previous context switch: "awsctl switch -"
        if target == "-":
            prev = get_previous_context()
            if not prev:
                utils.console.print("No previous context available.")
                return 1
            org_name = prev.get("current_org") or prev.get("org")
            account = prev.get("account")
            role = prev.get("role")
            region = prev.get("region")
            if not all([org_name, account, role, region]):
                utils.console.print(
                    "[red]Previous context is incomplete (missing fields).[/]"
                )
                return 1
            try:
                org_data = get_org(org_name)
            except Exception:
                org_data = {"name": org_name, "provider": "aws"}
            export_str = _self.emit_exports(org_data, account, role, region)
            print(export_str)
            save_context(org_name, account, role, region)
            utils.console.print(
                f"[bold green]✔ Switched to {account} / {role} / {region}[/]"
            )
            return 0

        # Handle alias switch: "awsctl switch @prod"
        if target and target.startswith("@"):
            alias_name = target[1:]
            cfg = core.load_orgs_config()
            if isinstance(cfg, dict):
                aliases = cfg.get("aliases", {})
            else:
                aliases = {}
            if alias_name not in aliases:
                utils.console.print(f"[red]Alias '@{alias_name}' not defined.[/]")
                return 1
            alias = aliases[alias_name]
            org_name = alias.get("org")
            account = alias.get("account")
            role = alias.get("role")
            region = alias.get("region")
            if not all([org_name, account, role, region]):
                utils.console.print(
                    f"[red]Alias '@{alias_name}' is missing required fields (org, account, role, region).[/]"
                )
                return 1
            try:
                org_data = get_org(org_name)
            except Exception:
                org_data = {"name": org_name, "provider": "aws"}
            export_str = _self.emit_exports(org_data, account, role, region)
            print(export_str)
            save_context(org_name, account, role, region)
            utils.console.print(
                f"[bold green]✔ Switched to {account} / {role} / {region}[/]"
            )
            return 0

        # Non-interactive / direct switch: explicit account+role+region provided
        account_arg = getattr(args, "account", None)
        role_arg = getattr(args, "role", None)
        region_arg = getattr(args, "region", None)
        org_name = getattr(args, "org", None)

        if not org_name:
            ctx = load_context()
            org_name = ctx.get("current_org") if ctx else None

        if account_arg and not role_arg:
            utils.console.print(
                "[red]--role is required when --account is specified.[/]"
            )
            return 1

        if org_name:
            try:
                org_data = get_org(org_name)
            except Exception:
                org_data = {"name": org_name, "provider": "aws"}
        else:
            cfg = load_config()
            orgs = [o["name"] for o in cfg.get("orgs", [])]
            if not orgs:
                utils.console.print(
                    "[red]No organizations configured.[/] Run [bold]awsctl init[/bold] or [bold]awsctl org add[/bold]."
                )
                return 1
            if len(orgs) == 1:
                org_name = orgs[0]
                try:
                    org_data = get_org(org_name)
                except Exception:
                    org_data = {"name": org_name, "provider": "aws"}
            else:
                try:
                    from InquirerPy import inquirer

                    org_name = inquirer.select(
                        message="Select Organization:", choices=orgs
                    ).execute()
                    try:
                        org_data = get_org(org_name)
                    except Exception:
                        org_data = {"name": org_name, "provider": "aws"}
                except KeyboardInterrupt:
                    raise

        # Guardrail: validate explicit region before proceeding.
        if region_arg:
            try:
                from .guardrails import validate_region

                validate_region(org_data, region_arg)
            except SystemExit:
                return 1

        account, role, region = _interactive.run_interactive_use(
            org_data,
            account_arg,
            role_arg,
            region_arg,
        )

        if not all([account, role, region]):
            return 1

        export_str = _self.emit_exports(org_data, account, role, region)
        print(export_str)
        save_context(org_name, account, role, region)
        utils.console.print(
            f"[bold green]✔ Switched to {account} / {role} / {region}[/]"
        )
        return 0
    except KeyboardInterrupt:
        utils.console.print("Operation cancelled")
        return 1
    except SystemExit:
        return 1
    except Exception as e:
        utils.console.print(f"Switch failed: {e}")
        return 1


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


def cmd_org(args: Any) -> int:
    from .commands.org import OrgAddCommand, OrgListCommand, OrgRemoveCommand

    sub = getattr(args, "org_command", None)
    if sub == "add":
        return OrgAddCommand().execute(args)
    elif sub == "list":
        return OrgListCommand().execute(args)
    elif sub == "remove":
        return OrgRemoveCommand().execute(args)
    else:
        console.print("Usage: awsctl org <add|list|remove>")
        return 1


def cmd_whoami(args: Any = None) -> int:
    """Show the active identity for the current provider context.

    Falls back to AWS STS when no context exists (backward-compat with
    tests and scripts that call whoami without a prior switch).
    """
    ctx = load_context()
    provider = ctx.get("provider", "aws") if ctx else "aws"
    org_name = ctx.get("current_org", "") if ctx else ""
    account = ctx.get("account", "") if ctx else ""
    role = ctx.get("role", "") if ctx else ""
    region = ctx.get("region", "") if ctx else ""

    if provider == "aws":
        from . import aws

        try:
            result = aws.run_aws(["sts", "get-caller-identity"])
            if result.get("returncode") != 0:
                utils.console.print(
                    f"Failed to get identity: {result.get('stderr', '')}"
                )
                return 1
            utils.console.print(result.get("stdout", ""))
        except Exception as e:
            utils.console.print(str(e))
            return 1
    elif provider == "azure":
        utils.console.print(
            f"[bold]Azure[/bold]  org={org_name}  "
            f"subscription={account}  role={role}  region={region}"
        )
    elif provider == "gcp":
        utils.console.print(
            f"[bold]GCP[/bold]  org={org_name}  "
            f"project={account}  role={role}  region={region}"
        )
    else:
        utils.console.print(
            f"[bold]{provider}[/bold]  org={org_name}  "
            f"account={account}  role={role}  region={region}"
        )
    return 0


def cmd_open(args: Any = None) -> int:
    """Open the cloud console for the active org and provider."""
    try:
        ctx = load_context()
        org_name = ctx.get("current_org") if ctx else None
        if not org_name:
            utils.console.print("[red]Error: No active context.[/]")
            return 1
        org = core.get_org(org_name)  # propagates to outer except → returns 1
        provider = org.get("provider", "aws")
        if provider == "aws":
            from .schema import AWS_PARTITIONS

            partition = org.get("partition", "aws")
            console_url = AWS_PARTITIONS.get(partition, AWS_PARTITIONS["aws"])[
                "console"
            ]
        elif provider == "azure":
            console_url = "https://portal.azure.com/"
        elif provider == "gcp":
            project = (ctx.get("account") if ctx else None) or org.get(
                "default_project", ""
            )
            console_url = (
                f"https://console.cloud.google.com/home/dashboard?project={project}"
                if project
                else "https://console.cloud.google.com/"
            )
        else:
            console_url = "https://console.aws.amazon.com/"

        import webbrowser

        webbrowser.open(console_url)
        return 0
    except Exception as e:
        utils.console.print(f"[red]Error: {e}[/]")
        return 1


def cmd_upgrade(args: Any = None) -> int:
    """Upgrade awsctl by downloading the latest release wheel from GitHub."""
    import json
    import subprocess
    import tempfile
    import urllib.error
    import urllib.request

    github_org = "BT-IT-Infrastructure-CloudOps"
    github_repo = "aws-terraform-infra-cloudops-awsctl"
    api_url = f"https://api.github.com/repos/{github_org}/{github_repo}/releases/latest"

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        console.print(
            "[red]GITHUB_TOKEN not set.[/] A GitHub PAT with [bold]read:contents[/bold] "
            "scope is required to download from the private repository.\n"
            "  export GITHUB_TOKEN=<your-PAT>   # then re-run: awsctl upgrade"
        )
        return 1

    console.print("[bold]Checking for latest release...[/]")
    try:
        req = urllib.request.Request(
            api_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        with urllib.request.urlopen(
            req
        ) as resp:  # nosec B310 — hardcoded HTTPS GitHub API URL
            release = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        console.print(
            f"[red]GitHub API error {exc.code}:[/] {exc.reason}\n"
            "Check that GITHUB_TOKEN has [bold]read:contents[/bold] scope."
        )
        return 1
    except Exception as exc:
        console.print(f"[red]Failed to query GitHub API:[/] {exc}")
        return 1

    tag = release.get("tag_name", "unknown")
    console.print(f"  Latest release: [bold]{tag}[/]")

    # Find the wheel asset in the release
    wheel_asset = next(
        (a for a in release.get("assets", []) if a["name"].endswith(".whl")),
        None,
    )
    if not wheel_asset:
        console.print(
            f"[red]No .whl asset found in release {tag}.[/]\n"
            "The release may not have been built yet — check GitHub Actions."
        )
        return 1

    # Download wheel to a temp file, then install
    wheel_name = wheel_asset["name"]
    asset_api_url = wheel_asset["url"]  # API URL, requires Accept: octet-stream

    console.print(f"  Downloading [bold]{wheel_name}[/]...")
    tmp_path: Optional[str] = None
    try:
        req = urllib.request.Request(
            asset_api_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/octet-stream",
            },
        )
        with urllib.request.urlopen(
            req
        ) as resp:  # nosec B310 — hardcoded HTTPS GitHub download URL
            wheel_data = resp.read()

        with tempfile.NamedTemporaryFile(suffix=".whl", delete=False) as f:
            f.write(wheel_data)
            tmp_path = f.name

        console.print("  Installing...")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                tmp_path,
                "--extra-index-url",
                "https://pypi.org/simple/",
            ],
            timeout=300,
        )
    except Exception as exc:
        console.print(f"[red]Download failed:[/] {exc}")
        return 1
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    if result.returncode == 0:
        console.print(f"[green]✅ awsctl upgraded to {tag} successfully.[/]")
        console.print("Restart your shell to pick up the new version.")
    else:
        console.print("[red]Upgrade failed.[/] Check pip output above.")
    return result.returncode


def cmd_setup(args: Any = None) -> int:
    """Run the setup wizard / merge defaults."""
    return core.cmd_setup()


def cmd_orgs(args: Any = None) -> int:
    """Alias for cmd_org."""
    return cmd_org(args)


def cmd_list(args: Any = None) -> int:
    """Dispatch 'list <resource>' subcommands."""
    resource = getattr(args, "resource", None)
    if resource == "orgs":
        return cmd_orgs(args)
    console.print(f"Unknown resource: {resource}")
    return 1


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
    lp.add_argument("--org", dest="org_flag", help="Organization name (flag form)")
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
    ip = sub.add_parser("init", help="Initialize configuration wizard")
    ip.add_argument(
        "--shell-only",
        action="store_true",
        dest="shell_only",
        help="Install shell integration only (no wizard)",
    )

    # upgrade
    sub.add_parser("upgrade", help="Upgrade awsctl from GitHub Packages")

    # org
    op = sub.add_parser("org", help="Manage cloud organizations")
    org_sub = op.add_subparsers(dest="org_command")
    add_p = org_sub.add_parser("add", help="Add a new organization")
    add_p.add_argument(
        "--provider", choices=["aws", "azure", "gcp"], help="Cloud provider"
    )
    add_p.add_argument("--name", help="Org slug name")
    org_sub.add_parser("list", help="List configured organizations")
    rm_p = org_sub.add_parser("remove", help="Remove an organization")
    rm_p.add_argument("name", help="Org name to remove")

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
    "org": "cmd_org",
    "orgs": "cmd_orgs",
    "list": "cmd_list",
    "setup": "cmd_setup",
    "whoami": "cmd_whoami",
    "open": "cmd_open",
    "upgrade": "cmd_upgrade",
}


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # Fast paths that don't need full argparse.
    # --check-strategy MUST be checked before --version: the shell wrapper calls
    # `_awsctl_bin --check-strategy --version` to probe the flag, and if --version
    # were checked first it would print the version string instead of EXEC/EVAL.
    if "--check-strategy" in argv:
        idx = argv.index("--check-strategy")
        cmd_arg = argv[idx + 1] if idx + 1 < len(argv) else ""
        sys.stdout.write(determine_strategy([cmd_arg]) + "\n")
        return 0

    if "--version" in argv:
        stdout_console.print(_resolved_version())
        return 0

    if "--help" in argv or "-h" in argv:
        stdout_console.print(
            "[bold]awsctl[/bold] — Enterprise Cloud Identity & Context Manager\n\n"
            "Commands: login, switch, logout, exec, status, accounts, doctor, init, org\n"
            "Options:  --version, --help, --check-strategy <cmd>"
        )
        return 0

    # TTY guard — warn when --eval is used without the shell wrapper context.
    # The shell wrapper sets AWSCTL_WRAPPER_ACTIVE=1 before calling us.
    # Direct invocation with --eval risks exposing credentials in shell history
    # or redirecting them to a file.
    eval_mode = "--eval" in argv
    argv = [a for a in argv if a != "--eval"]
    if eval_mode and not os.environ.get("AWSCTL_WRAPPER_ACTIVE"):
        sys.stderr.write(
            "awsctl: WARNING — --eval used outside shell wrapper context.\n"
            "  Credentials will be printed to stdout and may leak into shell\n"
            "  history or redirected files. Run 'awsctl init' to install the\n"
            "  shell wrapper, or set AWSCTL_WRAPPER_ACTIVE=1 to suppress.\n"
        )

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
