# file: src/awsctl/cli.py
# SPDX-License-Identifier: MIT
"""
awsctl CLI entrypoint.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Union, cast

from rich.markdown import Markdown
from rich.table import Table

from awsctl import cli_accounts, context_manager, core, doctor, guardrails, wizard
from awsctl.accounts import Account, list_accounts
from awsctl.help_text import HELP_MARKDOWN
from awsctl.sso_cache import OrgRef
from awsctl.use_exports import emit_exports
from awsctl.utils import console, debug_print, open_browser, set_debug, stdout_console

CONTEXT_FILE = Path.home() / ".aws" / "awsctl-context.json"


@contextlib.contextmanager
def secure_stdout() -> Generator[Any, None, None]:
    """
    🛡️ SECURITY: Redirect stdout to stderr by default to prevent Eval Injection.
    """
    is_test = os.environ.get("AWSCTL_TEST_MODE") == "1"
    real_stdout = sys.stdout

    if not is_test:
        sys.stdout = sys.stderr

    try:
        yield real_stdout
    finally:
        if not is_test:
            sys.stdout = real_stdout


def _resolved_version() -> str:
    try:
        from importlib.metadata import version as pkg_version

        return pkg_version("awsctl").strip()
    except Exception:
        return "0.0.0"


def load_context() -> Dict[str, Any]:
    if not CONTEXT_FILE.exists():
        return {}
    try:
        data: Dict[str, Any] = json.loads(CONTEXT_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        return data
    except Exception as e:
        debug_print(f"Failed to load context: {e}")
        return {}


def print_rich_help() -> None:
    md = Markdown(HELP_MARKDOWN)
    stdout_console.print(md)


def determine_strategy(argv: List[str]) -> str:
    """
    Determine if the command should EXEC (run) or EVAL (modify shell).
    """
    if "-h" in argv or "--help" in argv:
        return "EXEC"

    # Filter out global flags that might confuse positional detection
    clean_argv = []
    for arg in argv:
        if arg == "--":
            break
        if not arg.startswith("--debug"):
            clean_argv.append(arg)

    # Find the subcommand (first non-flag argument)
    cmds = [arg for arg in clean_argv if not arg.startswith("-")]
    if not cmds:
        return "EXEC"

    cmd = cmds[0]

    # Commands that ALWAYS modify the shell environment
    if cmd in ("switch", "use", "logout"):
        return "EVAL"

    # Login is special:
    # 'awsctl login' -> EXEC (Interactive/Browser)
    # 'awsctl login --account ...' -> EVAL (Chain context switch)
    if cmd == "login":
        # [FIX] Robust check for context flags, handling both "--flag value" and "--flag=value"
        trigger_prefixes = ("--account", "-a", "--role", "-r", "--region")

        for arg in argv:
            # Check exact match (e.g. '--account' '123')
            if arg in trigger_prefixes:
                return "EVAL"
            # Check prefix match (e.g. '--account=123')
            for prefix in trigger_prefixes:
                if arg.startswith(prefix + "="):
                    return "EVAL"

        return "EXEC"

    return "EXEC"


def cmd_whoami() -> int:
    with console.status("[dim]Querying STS...[/]"):
        try:
            p = core.run_aws(["aws", "sts", "get-caller-identity", "--output", "json"])
            if p.returncode != 0:
                console.print(f"[red]✗ Failed to get identity:[/]\n{p.stderr.strip()}\n{p.stdout.strip()}")
                return 1
            stdout_console.print_json(p.stdout.strip())
            return 0
        except Exception as e:
            console.print(f"[red]✗ Error: {e}[/]")

    return 1


def cmd_open() -> int:
    ctx = load_context()
    current_org = ctx.get("current_org")
    if not current_org:
        console.print("[yellow]No active session.[/] Run `awsctl login`.")
        return 1
    try:
        cfg = core.load_orgs_config()
        ref = _get_org_ref(cfg, current_org)

        console.print(f"Opening [link={ref.sso_start_url}]{ref.sso_start_url}[/] ...")
        open_browser(ref.sso_start_url)
        return 0
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1


def cmd_env() -> int:
    # 🛡️ SMART SECURITY:
    # Determine where stdout is pointing.
    # If it's a TTY (screen), we ENFORCE the guard (safe_output=True).
    # If it's a Pipe/File (script/redirection), we BYPASS the guard (safe_output=False).
    is_tty = sys.stdout.isatty()

    sys.stdout.write(core.cmd_env(safe_output=is_tty))
    return 0


def cmd_status() -> int:
    context_manager.print_status()
    return 0


def cmd_orgs(args: Union[object, None]) -> int:
    cfg = core.load_orgs_config()
    orgs = cfg.get("orgs", [])
    if getattr(args, "json", False):
        print(json.dumps(orgs, indent=2))
        return 0
    if not orgs:
        console.print("[yellow]No organizations configured.[/]")
        return 0
    table = Table(title="Enabled Organizations", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Region", style="magenta")
    for o in orgs:
        table.add_row(
            str(o.get("name", "N/A")),
            str(o.get("description", "")),
            str(o.get("sso_region", "-")),
        )

    stdout_console.print(table)
    return 0


def _resolve_account_id(ref: OrgRef, target: Optional[str]) -> str:
    if not target:
        raise SystemExit("No account specified.")

    if target.isdigit() and len(target) == 12:
        return target

    accts: List[Account] = list_accounts(ref)
    target_lower = target.lower()

    for a in accts:
        if a.account_name.lower() == target_lower:
            return cast(str, a.account_id)

    for a in accts:
        if a.account_id == target:
            return cast(str, a.account_id)

    raise SystemExit(f"Account '{target}' not found.")


def cmd_login(args: argparse.Namespace) -> int:
    org_name = getattr(args, "org", None)
    if not org_name:
        ctx = load_context()
        org_name = ctx.get("current_org")

    if not org_name:
        console.print("[red]Error: Could not determine organization. Use --org.[/]")
        return 1

    force = getattr(args, "force", False)

    rc = core.cmd_login(org_name, force=force)
    if rc != 0:
        return int(rc)

    try:
        context_manager.save_context_update(org=org_name)
    except Exception as e:
        debug_print(f"Failed to save context after login: {e}")

    account = getattr(args, "account", None)
    role = getattr(args, "role", None)

    if account or role:
        if account:
            try:
                cfg = core.load_orgs_config()
                ref = _get_org_ref(cfg, org_name)
                args.target = _resolve_account_id(ref, str(account))
            except (Exception, SystemExit):
                # [FIX] Bandit B110
                debug_print("Account resolution failed, falling back to raw ID")
                args.target = account

        return cmd_switch(args)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    try:
        cfg = core.load_orgs_config()
        ctx = context_manager.load_context()
        current_org = ctx.get("current_org")
        as_json = getattr(args, "json", False)

        if args.resource == "orgs":
            return cmd_orgs(args)

        if args.resource == "accounts":
            if not current_org:
                console.print("[bold red]No active org. Run `awsctl login` first.[/]")
                return 1
            return int(cli_accounts.cmd_accounts(cfg, str(current_org), as_json))

        if args.resource == "roles":
            if not current_org:
                console.print("[bold red]No active org. Run `awsctl login` first.[/]")
                return 1
            account = ctx.get("account")
            if not account:
                console.print("[bold red]No account selected. Use `awsctl switch` first.[/]")
                return 1
            return int(cli_accounts.cmd_roles(cfg, str(current_org), str(account), as_json))
    except Exception as e:
        debug_print(f"List error: {e}")
        console.print(f"[red]Error listing resources: {e}[/]")
        return 1

    return 0


def cmd_switch(args: argparse.Namespace) -> int:
    with secure_stdout() as safe_out:
        ctx = context_manager.load_context()
        current_org = getattr(args, "org", None) or ctx.get("current_org")
        target = getattr(args, "target", None)

        try:
            # 1. Toggle Mode
            if target == "-":
                prev = context_manager.get_previous_context()
                if not prev:
                    console.print("[red]No previous context to switch to.[/]")
                    return 1

                account = prev.get("account")
                role = prev.get("role")
                region = prev.get("region")
                org_name = prev.get("org")

                if not (account and role and region and org_name):
                    console.print("[red]Previous context is incomplete.[/]")
                    return 1

                try:
                    org_data = core.get_org(org_name)
                except (SystemExit, Exception):
                    console.print(f"[red]Previous org '{org_name}' no longer exists.[/]")
                    return 1

                # Security Checks for Toggle
                guardrails.check_min_version(org_data)
                guardrails.check_break_glass(org_data, str(role))

                ref = OrgRef(org_data["name"], org_data["sso_start_url"], org_data["sso_region"])

                export_cmd = emit_exports(ref, str(account), str(role), str(region), safe_output=True)

                context_manager.save_context_update(org=org_name, account=account, role=role, region=region)
                safe_out.write(export_cmd)
                return 0

            # 2. Alias Mode (Quick Switch)
            if target and target.startswith("@"):
                alias_name = target[1:]
                cfg = core.load_orgs_config()
                aliases = cfg.get("aliases", {})
                definition = aliases.get(alias_name)

                if not definition:
                    console.print(f"[red]Alias '@{alias_name}' not defined in orgs.yaml[/]")
                    return 1

                required_fields = ["org", "account", "role", "region"]
                if not all(k in definition for k in required_fields):
                    console.print(f"[red]Alias '@{alias_name}' is missing required fields " "(org, account, role, region).[/]")
                    return 1

                current_org = definition["org"]
                account = str(definition["account"])
                role = definition["role"]
                region = definition["region"]

                try:
                    org_data = core.get_org(current_org)
                except (SystemExit, ValueError):
                    console.print(f"[red]Org '{current_org}' in alias is not enabled or invalid.[/]")
                    return 1

                # Security Checks for Alias
                guardrails.check_min_version(org_data)
                guardrails.validate_region(org_data, region)
                guardrails.check_break_glass(org_data, role)

                ref = OrgRef(org_data["name"], org_data["sso_start_url"], org_data["sso_region"])

                export_cmd = emit_exports(ref, str(account), str(role), str(region), safe_output=True)

                context_manager.save_context_update(org=current_org, account=account, role=role, region=region)
                safe_out.write(export_cmd)
                return 0

            legacy_account = getattr(args, "account", None)

            # 3. Interactive Mode
            if not target and not legacy_account:
                if not current_org:
                    console.print("[red]No active org. Run `awsctl login` first.[/]")
                    return 1
                from .interactive import run_interactive_use

                role = getattr(args, "role", None)
                region = getattr(args, "region", None)

                # Security checks happen inside run_interactive_use now (for UX flow)
                account, role, region = run_interactive_use(current_org, preselected_role=role, preselected_region=region)

                ref = _get_org_ref(core.load_orgs_config(), current_org)
                export_cmd = emit_exports(ref, account, role, region, safe_output=True)

                context_manager.save_context_update(org=current_org, account=account, role=role, region=region)
                safe_out.write(export_cmd)
                return 0

            # 4. Explicit / Non-Interactive Mode
            raw_account = target or legacy_account

            org_conf = core.get_org(current_org)
            ref = _get_org_ref(core.load_orgs_config(), current_org)

            try:
                if raw_account and raw_account.isdigit() and len(raw_account) == 12:
                    account = raw_account
                else:
                    account = _resolve_account_id(ref, raw_account)
            except (SystemExit, Exception) as e:
                console.print(f"[red]Resolution Error: {e}[/]")
                return 1

            role = getattr(args, "role", None)
            region = getattr(args, "region", None)

            if not role:
                console.print("[red]Switching non-interactively requires --role.[/]")
                return 1
            if not region:
                region = org_conf.get("default_region", "us-east-1")

            # Security Checks for Explicit Mode
            guardrails.check_min_version(org_conf)
            guardrails.validate_region(org_conf, str(region))
            guardrails.check_break_glass(org_conf, str(role))

            export_cmd = emit_exports(ref, str(account), str(role), str(region), safe_output=True)

            context_manager.save_context_update(org=current_org, account=account, role=role, region=region)
            safe_out.write(export_cmd)
            return 0

        except KeyboardInterrupt:
            console.print("[yellow]\nOperation cancelled.[/]")
            return 1
        except SystemExit as e:
            if e.code != 0:
                console.print(f"[red]Switch failed: {e.code}[/]")
                if "token" in str(e.code).lower():
                    console.print("[yellow]Hint: Run `awsctl login` to refresh.[/]")
            return 1
        except Exception as e:
            console.print(f"[red]Switch failed: {e}[/]")
            return 1


def cmd_exec(args: argparse.Namespace) -> int:
    ctx = load_context()
    account = getattr(args, "account", None) or ctx.get("account")
    role = getattr(args, "role", None) or ctx.get("role")
    region = getattr(args, "region", None) or ctx.get("region")
    current_org = ctx.get("current_org")

    if not region and current_org:
        try:
            org_conf = core.get_org(current_org)
            region = org_conf.get("default_region", "us-east-1")
        except Exception:
            # [FIX] Bandit B110: Log lookup failure
            debug_print("Default region lookup failed")

    if not current_org:
        console.print("[red]No active org. Run `awsctl login` first.[/]")
        return 1

    cfg = core.load_orgs_config()
    ref = _get_org_ref(cfg, current_org)

    # Security: Check Version
    try:
        org_data = core.get_org(current_org)
        guardrails.check_min_version(org_data)
        # We don't check break-glass on exec yet to avoid blocking automation,
        # but region guardrails are checked by token scope implicitly.
    except Exception as e:
        # [FIX] Bandit B110: Log the error
        debug_print(f"Exec version check skipped: {e}")

    if account and not account.isdigit():
        try:
            account = _resolve_account_id(ref, str(account))
        except Exception:
            # [FIX] Bandit B110
            debug_print("Account resolution fail in exec")

    if not (account and role and region):
        console.print("[red]Error: Missing context. Provide --account/--role/--region or switch context first.[/]")
        return 1

    cmd_list = args.command
    if cmd_list and cmd_list[0] == "--":
        cmd_list = cmd_list[1:]
    if not cmd_list:
        console.print("[red]Error: No command specified.[/]")
        return 1
    return int(core.cmd_exec(str(account), str(role), str(region), cmd_list))


def cmd_setup(args: Union[object, None]) -> int:
    if os.environ.get("CI") or os.environ.get("AWSCTL_HEADLESS"):
        # [FIX] Use rich console print to avoid encoding errors on Windows/Legacy terminals
        console.print("⚡ Headless mode detected.")
        return int(core.cmd_setup())
    try:
        # [FIX] PYBH-0042: Check return value
        success = wizard.run_wizard()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\nSetup cancelled.")
        return 1
    except Exception as e:
        print(f"✗ Setup failed: {e}", file=sys.stderr)
        return 1


def cmd_doctor(args: Union[object, None]) -> int:
    return int(doctor.run_diagnostics(getattr(args, "fix_path", False)))


def _get_org_ref(cfg: Dict[str, Any], name: Optional[str]) -> OrgRef:
    if not cfg.get("orgs"):
        sys.exit("No orgs configured.")
    org_name = name or cfg["orgs"][0]["name"]
    for o in cfg["orgs"]:
        if o.get("name") == org_name:
            return OrgRef(o["name"], o["sso_start_url"], o["sso_region"])
    sys.exit(f"Org not found: {org_name}")


def main(argv: Union[list[str], None] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    p = argparse.ArgumentParser(prog="awsctl", add_help=False)
    p.add_argument("--debug", action="store_true")
    p.add_argument("--version", "-V", action="store_true")
    p.add_argument("--help", "-h", action="store_true")
    p.add_argument("--whoami", action="store_true")
    p.add_argument("--open", action="store_true")
    p.add_argument("--matrix", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--check-strategy", action="store_true", help=argparse.SUPPRESS)

    sub = p.add_subparsers(dest="sub")
    sub.add_parser("setup")
    sub.add_parser("doctor")
    sub.add_parser("env")
    sub.add_parser("cache-clear")
    sub.add_parser("refresh")

    login = sub.add_parser("login")
    login.add_argument("--org", required=False, help="Organization name")
    login.add_argument("--account", "-a", help="Account ID/Name")
    login.add_argument("--role", "-r", help="Role Name")
    login.add_argument("--region", help="Region")
    login.add_argument("--force", action="store_true", help="Force login")

    sub.add_parser("logout")

    switch = sub.add_parser("switch")
    switch.add_argument("target", nargs="?", help="Account name or ID or '-'")
    switch.add_argument("--role", "-r", help="Target role")
    switch.add_argument("--region", help="Target region")
    switch.add_argument("--account", "-a", help=argparse.SUPPRESS)

    use = sub.add_parser("use")
    use.add_argument("--account", "-a", required=False)
    use.add_argument("--role", "-r", required=False)
    use.add_argument("--region", required=False)

    sub.add_parser("status")
    sub.add_parser("console")

    list_p = sub.add_parser("list")
    list_p.add_argument("resource", choices=["orgs", "accounts", "roles"])
    list_p.add_argument("--json", action="store_true", help="Output in JSON format")

    exec_p = sub.add_parser("exec")
    exec_p.add_argument("--account", help="Target Account ID/Name")
    exec_p.add_argument("--role", help="Role to assume")
    exec_p.add_argument("--region", help="Region")
    exec_p.add_argument("command", nargs=argparse.REMAINDER, help="Command to run")

    try:
        args, unknown = p.parse_known_args(argv)

        if args.check_strategy:
            real_args = [a for a in argv if a != "--check-strategy"]
            print(determine_strategy(real_args))
            return 0

        if args.debug:
            set_debug(True)

        if args.version:
            stdout_console.print(f"awsctl [bold cyan]v{_resolved_version()}[/]")
            return 0

        if args.help or (not args.sub and not args.whoami and not args.open and not args.matrix):
            print_rich_help()
            return 0

        if args.sub == "setup":
            return cmd_setup(args)
        if args.sub == "doctor":
            return cmd_doctor(args)
        if args.sub == "env":
            return cmd_env()
        if args.sub == "status":
            return cmd_status()
        if args.sub == "console":
            return cmd_open()
        if args.sub == "login":
            return cmd_login(args)
        if args.sub == "logout":
            sys.stdout.write(core.cmd_logout_str())
            return 0
        if args.sub in ("refresh", "cache-clear"):
            return int(core.cmd_cache_clear())

        if args.sub in ("switch", "use"):
            return cmd_switch(args)
        if args.sub == "exec":
            return cmd_exec(args)
        if args.sub == "list":
            return cmd_list(args)
        if getattr(args, "whoami", False):
            return cmd_whoami()
        if getattr(args, "open", False):
            return cmd_open()
        if getattr(args, "matrix", False):
            from .cool_features import run_matrix_login

            run_matrix_login()
            return 0

    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled.[/]")
        return 1
    except Exception as e:
        console.print(f"[red]Fatal Error: {e}[/]")
        return 1

    return 0
