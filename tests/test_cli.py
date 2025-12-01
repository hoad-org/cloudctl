# file: src/awsctl/cli.py
# SPDX-License-Identifier: MIT
"""
awsctl CLI entrypoint.
v1.3.0 Universal Wrapper Edition.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from rich.markdown import Markdown
from rich.table import Table

# Use absolute imports
from awsctl import cli_accounts, context_manager, core, guardrails, wizard
from awsctl.accounts import list_accounts
from awsctl.help_text import HELP_MARKDOWN
from awsctl.sso_cache import OrgRef
from awsctl.use_exports import emit_exports
from awsctl.utils import console, open_browser, set_debug

CONTEXT_FILE = Path.home() / ".aws" / "awsctl-context.json"


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
        return json.loads(CONTEXT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def print_rich_help() -> None:
    md = Markdown(HELP_MARKDOWN)
    console.print(md)


def determine_strategy(argv: List[str]) -> str:
    if not argv:
        return "EXEC"

    cmd = argv[0]
    if cmd in ("switch", "use", "logout"):
        return "EVAL"
    if cmd == "login":
        switch_flags = {"--account", "--role", "--region", "-a", "-r"}
        if any(arg in switch_flags for arg in argv[1:]):
            return "EVAL"
        return "EXEC"
    return "EXEC"


def cmd_whoami() -> int:
    with console.status("[dim]Querying STS...[/]"):
        try:
            p = core.run_aws(["aws", "sts", "get-caller-identity", "--output", "json"])
            if p.returncode != 0:
                console.print(f"[red]✗ Failed to get identity:[/]\n{p.stderr.strip()}")
                return 1
            console.print_json(p.stdout.strip())
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
        console.print(f"[red]Error:[/ {e}")
        return 1


def cmd_env() -> int:
    sys.stdout.write(core.cmd_env())
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
    table = Table(
        title="Enabled Organizations", show_header=True, header_style="bold cyan"
    )
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Region", style="magenta")
    for o in orgs:
        table.add_row(
            o.get("name", "N/A"), o.get("description", ""), o.get("sso_region", "-")
        )
    console.print(table)
    return 0


def _resolve_account_id(ref: OrgRef, target: Optional[str]) -> str:
    if not target:
        raise SystemExit("No account specified.")
    if target.isdigit() and len(target) == 12:
        return target
    accts = list_accounts(ref)
    target_lower = target.lower()
    for a in accts:
        if a.account_name.lower() == target_lower:
            return a.account_id
        if a.account_id == target:
            return a.account_id
    raise SystemExit(f"Account '{target}' not found.")


def cmd_login(args: argparse.Namespace) -> int:
    org_name = getattr(args, "org", None)
    if not org_name:
        ctx = load_context()
        org_name = ctx.get("current_org")
    if not org_name:
        try:
            cfg = core.load_orgs_config()
            if cfg.get("orgs"):
                org_name = cfg["orgs"][0]["name"]
        except Exception:
            pass

    if not org_name:
        console.print("[red]Error: Could not determine organization. Use --org.[/]")
        return 1

    rc = core.cmd_login(org_name)
    if rc != 0:
        return rc

    try:
        context_manager.save_context_update(org=org_name)
    except Exception:
        pass

    account = getattr(args, "account", None)
    role = getattr(args, "role", None)

    # Handle Command Chaining
    if account or role:
        if account:
            try:
                cfg = core.load_orgs_config()
                ref = _get_org_ref(cfg, org_name)
                args.target = _resolve_account_id(ref, str(account))
            except Exception as e:
                # Fallback: if resolution fails (e.g. timeout), pass raw arg
                # but it might fail later in switch if it's not an ID
                console.print(
                    f"[warning]Account resolution warning: {e}. Trying raw ID.[/]"
                )
                args.target = account
        return cmd_switch(args)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
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
        return cli_accounts.cmd_accounts(cfg, current_org, as_json)

    if args.resource == "roles":
        if not current_org:
            console.print("[bold red]No active org. Run `awsctl login` first.[/]")
            return 1
        account = ctx.get("account")
        if not account:
            console.print(
                "[bold red]No account selected. Use `awsctl switch` first.[/]"
            )
            return 1
        return cli_accounts.cmd_roles(cfg, current_org, account, as_json)

    return 0


def cmd_switch(args: argparse.Namespace) -> int:
    ctx = context_manager.load_context()
    current_org = getattr(args, "org", None) or ctx.get("current_org")
    target = getattr(args, "target", None)

    try:
        if target == "-":
            prev = context_manager.get_previous_context()
            if not prev:
                console.print("[red]No previous context to switch to.[/]")
                return 1
            account = prev.get("account")
            role = prev.get("role")
            region = prev.get("region")
            org_name = prev.get("org")

            # Validate Org existence to prevent crashing if config changed
            try:
                org_data = core.get_org(org_name)
            except SystemExit:
                console.print(f"[red]Previous org '{org_name}' no longer exists.[/]")
                return 1

            ref = OrgRef(
                org_data["name"], org_data["sso_start_url"], org_data["sso_region"]
            )

            sys.stdout.write(emit_exports(ref, str(account), str(role), str(region)))
            context_manager.save_context_update(
                org=org_name, account=account, role=role, region=region
            )
            return 0

        legacy_account = getattr(args, "account", None)

        # Interactive Mode
        if not target and not legacy_account:
            if not current_org:
                console.print("[red]No active org. Run `awsctl login` first.[/]")
                return 1
            from .interactive import run_interactive_use

            account, role, region = run_interactive_use(current_org)
            ref = _get_org_ref(core.load_orgs_config(), current_org)
            sys.stdout.write(emit_exports(ref, account, role, region))
            context_manager.save_context_update(
                org=current_org, account=account, role=role, region=region
            )
            return 0

        # Explicit / Non-Interactive Mode
        raw_account = target or legacy_account
        ref = _get_org_ref(core.load_orgs_config(), current_org)

        try:
            account = _resolve_account_id(ref, raw_account)
        except SystemExit as se:
            console.print(f"[red]{se}[/]")
            return 1
        except Exception as e:
            console.print(f"[red]Resolution Error: {e}[/]")
            return 1

        role = getattr(args, "role", None)
        region = getattr(args, "region", None)
        if not role:
            console.print("[red]Switching non-interactively requires --role.[/]")
            return 1
        if not region:
            org = core.get_org(current_org)
            region = org.get("default_region", "us-east-1")

        org_conf = core.get_org(current_org)
        guardrails.validate_region(org_conf, str(region))
        sys.stdout.write(emit_exports(ref, str(account), str(role), str(region)))
        context_manager.save_context_update(
            org=current_org, account=account, role=role, region=region
        )
        return 0

    except KeyboardInterrupt:
        # Exit silently to stderr so eval doesn't break
        console.print("[yellow]\nOperation cancelled.[/]")
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
            pass

    if not current_org:
        console.print("[red]No active org. Run `awsctl login` first.[/]")
        return 1

    cfg = core.load_orgs_config()
    ref = _get_org_ref(cfg, current_org)
    if account:
        try:
            account = _resolve_account_id(ref, str(account))
        except Exception:
            pass

    if not (account and role and region):
        console.print(
            "[red]Error: Missing context. Provide --account/--role/--region or switch context first.[/]"
        )
        return 1

    cmd_list = args.command
    if cmd_list and cmd_list[0] == "--":
        cmd_list = cmd_list[1:]
    if not cmd_list:
        console.print("[red]Error: No command specified.[/]")
        return 1
    return core.cmd_exec(str(account), str(role), str(region), cmd_list)


def cmd_setup(args: Union[object, None]) -> int:
    if os.environ.get("CI") or os.environ.get("AWSCTL_HEADLESS"):
        print("⚡ Headless mode detected.")
        return core.cmd_setup()
    try:
        wizard.run_wizard()
        return 0
    except KeyboardInterrupt:
        print("\nSetup cancelled.")
        return 1
    except Exception as e:
        print(f"✗ Setup failed: {e}", file=sys.stderr)
        return 1


def cmd_doctor(args: Union[object, None]) -> int:
    return int(core.cmd_doctor(getattr(args, "fix_path", False)))


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
    if "--check-strategy" in argv:
        real_args = [a for a in argv if a != "--check-strategy"]
        print(determine_strategy(real_args))
        return 0
    if "--debug" in argv:
        set_debug(True)
    if "-h" in argv or "--help" in argv:
        print_rich_help()
        return 0
    if any(flag in argv for flag in ("--version", "-V")):
        console.print(f"awsctl [bold cyan]v{_resolved_version()}[/]")
        return 0

    p = argparse.ArgumentParser(prog="awsctl", add_help=False)
    p.add_argument("--debug", action="store_true")
    p.add_argument("--whoami", action="store_true")
    p.add_argument("--open", action="store_true")
    p.add_argument("--matrix", action="store_true", help=argparse.SUPPRESS)

    sub = p.add_subparsers(dest="sub")
    sub.add_parser("setup")
    sub.add_parser("doctor")
    sub.add_parser("env")
    sub.add_parser("cache-clear")
    sub.add_parser("refresh")

    login = sub.add_parser("login")
    login.add_argument("--org", required=False, help="Organization name")
    login.add_argument("--account", help="Account ID/Name (Triggers context switch)")
    login.add_argument("--role", help="Role Name")
    login.add_argument("--region", help="Region")

    sub.add_parser("logout")

    switch = sub.add_parser("switch")
    switch.add_argument("target", nargs="?", help="Account name or ID or '-'")
    switch.add_argument("--role", help="Target role")
    switch.add_argument("--region", help="Target region")
    switch.add_argument("--account", help=argparse.SUPPRESS)

    use = sub.add_parser("use")
    use.add_argument("--account", required=False)
    use.add_argument("--role", required=False)
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

    args, unknown = p.parse_known_args(argv)

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
        return core.cmd_cache_clear()
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
    print_rich_help()
    return 0
