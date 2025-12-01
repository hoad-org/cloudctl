# file: src/awsctl/core.py
# SPDX-License-Identifier: MIT
"""
awsctl.core — Orchestrator module.
"""
from __future__ import annotations

import os
import pathlib as pathlib  # noqa: F401
import shutil
import subprocess
from typing import Any, Dict, List, Union

import yaml
from rich.panel import Panel

from awsctl import aws, config, doctor, plugins, shell
from awsctl.sso_cache import OrgRef, load_active_sso_token
from awsctl.use_exports import emit_unset
from awsctl.utils import console, debug_print

# Re-exports
HOME = config.HOME
ORGS_USER = config.ORGS_USER
AWS_DIR = aws.AWS_DIR
AWS_CONFIG = aws.AWS_CONFIG
SSO_CACHE_DIR = aws.SSO_CACHE_DIR

get_orgs_path = config.get_orgs_path
sample_orgs_yaml = config.sample_orgs_yaml
load_orgs_config = config.load_orgs_config
load_user_config = config.load_user_config
get_org = config.get_org

run_aws = aws.run_aws
ensure_sso_base_profile = aws.ensure_sso_base_profile
write_target_profile = aws.write_target_profile
aws_configure_set = aws.aws_configure_set
get_valid_sso_access_token = aws.get_valid_sso_access_token
sso_list_accounts = aws.sso_list_accounts
sso_list_account_roles = aws.sso_list_account_roles


def cmd_login(org: Union[str, None]) -> int:
    """Perform SSO login for the specified org."""
    try:
        o: Dict[str, Any] = config.get_org(org)
    except SystemExit as e:
        console.print(f"[error]{e}[/]")
        return 1

    # 1. Pre-Check: Is the token already valid?
    ref = OrgRef(o["name"], o["sso_start_url"], o["sso_region"])
    existing_token = load_active_sso_token(ref, raise_error=False)

    if existing_token:
        expiry_str = existing_token.expires_at.strftime("%H:%M UTC")
        console.print(
            Panel(
                f"[bold green]✔ Already logged in[/]\n\n"
                f"Organization: [bold white]{o['name']}[/]\n"
                f"Valid until:  [dim]{expiry_str}[/]",
                title="SSO Session Valid",
                border_style="green",
                expand=False,
            )
        )
        return 0

    # 2. Plugin Hook
    # [FIX] Merge Registry-enforced plugins with User-enabled plugins
    cfg = config.load_orgs_config()

    # Plugins defined in the Registry (Mandatory)
    registry_plugins = o.get("plugins", [])

    # Plugins enabled in User Config (Optional)
    user_plugins = cfg.get("plugins", {}).get("enabled", [])

    # Combine unique, keeping Registry plugins first for priority
    all_plugins = list(dict.fromkeys(registry_plugins + user_plugins))

    if all_plugins:
        with console.status("[bold blue]Running security plugins...[/]"):
            mods = plugins.load_plugins(all_plugins)
            plugins.call_hook(mods, "pre_login", org=o)

    profile = aws.ensure_sso_base_profile(o)

    console.print(
        Panel(
            f"authenticating to [bold cyan]{o['name']}[/]\n"
            f"URL: [underline]{o['sso_start_url']}[/]",
            title="AWS SSO Login",
            border_style="blue",
        )
    )

    # Disable timeout for login because it involves user interaction (browser)
    p = aws.run_aws(["aws", "sso", "login", "--profile", profile], timeout=None)

    if p.returncode != 0:
        console.print(f"[error]Login failed:[/]\n{p.stderr}")
        return 1

    console.print(
        Panel(
            "[bold green]✔ Login Successful[/]\n\n"
            "You can now run:\n"
            "  [bold white on black] awsctl switch [/]",
            title="Ready",
            border_style="green",
            expand=False,
        )
    )
    return 0


def cmd_logout() -> int:
    """Clear SSO cache (Internal Logic)."""
    with console.status("[bold red]Clearing SSO sessions...[/]"):
        aws.run_aws(["aws", "sso", "logout"])
        if SSO_CACHE_DIR.exists():
            for f in SSO_CACHE_DIR.glob("*.json"):
                f.unlink()
    return 0


def cmd_logout_str() -> str:
    """Return shell unsets."""
    cmd_logout()
    return str(emit_unset())


def cmd_cache_clear() -> int:
    """Bust AWS CLI account cache."""
    cache_dir = AWS_DIR / "cli" / "cache"
    if cache_dir.exists():
        with console.status("[bold yellow]Flushing AWS CLI cache...[/]"):
            shutil.rmtree(cache_dir)
            cache_dir.mkdir()
    console.print("[success]✔ Cache cleared.[/]")
    return 0


def cmd_exec(account: str, role: str, region: str, command: List[str]) -> int:
    """Run a command in a specific context without switching shell."""
    from .context_manager import load_context
    from .use_exports import _aws_json

    ctx = load_context()
    org_name = ctx.get("current_org")
    if not org_name:
        console.print("[error]No active org. Run `awsctl login` first.[/]")
        return 1

    try:
        org_conf = config.get_org(org_name)
        ref = OrgRef(
            org_conf["name"], org_conf["sso_start_url"], org_conf["sso_region"]
        )

        tok = load_active_sso_token(ref)
        data = _aws_json(
            [
                "aws",
                "sso",
                "get-role-credentials",
                "--region",
                tok.region,
                "--access-token",
                tok.access_token,
                "--account-id",
                account,
                "--role-name",
                role,
            ]
        )
        creds = data.get("roleCredentials") or {}

        if not creds:
            console.print("[error]Failed to get credentials.[/]")
            return 1

        env = os.environ.copy()
        env["AWS_ACCESS_KEY_ID"] = creds["accessKeyId"]
        env["AWS_SECRET_ACCESS_KEY"] = creds["secretAccessKey"]
        env["AWS_SESSION_TOKEN"] = creds["sessionToken"]
        env["AWS_REGION"] = region
        env["AWS_DEFAULT_REGION"] = region
        env.pop("AWS_PROFILE", None)

        debug_print(f"Context: {account} / {role} / {region}")
        console.print(f"[dim]Running command in account {account}...[/]")
        return int(subprocess.run(command, env=env, check=False).returncode)

    except Exception as e:
        console.print(f"[error]Exec failed: {e}[/]")
        return 1


def cmd_env() -> str:
    """Return current environment variables as a string (machine readable)."""
    from .context_manager import load_context

    ctx = load_context()
    if not all(k in ctx for k in ("current_org", "account", "role", "region")):
        return "# No active context"

    try:
        org_conf = config.get_org(ctx["current_org"])
        ref = OrgRef(
            org_conf["name"], org_conf["sso_start_url"], org_conf["sso_region"]
        )
        from .use_exports import emit_exports

        return emit_exports(ref, ctx["account"], ctx["role"], ctx["region"])
    except Exception as e:
        return f"# Error generating env: {e}"


def cmd_config_sync() -> int:
    """Synchronize ~/.aws/config with orgs.yaml."""
    with console.status("[bold green]Synchronizing AWS Profiles...[/]"):
        data = config.load_orgs_config()
        orgs = data.get("orgs", [])
        for o in orgs:
            if {"name", "sso_start_url", "sso_region"} <= set(o):
                aws.ensure_sso_base_profile(o)

    console.print(
        f"[success]✔ Synchronized {len(orgs)} org(s) into {aws.AWS_CONFIG}[/]"
    )
    return 0


def cmd_setup() -> int:
    """Headless setup logic."""
    p = config.get_orgs_path(ensure=True)
    try:
        present = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        present = {}

    if (not p.exists()) or not present.get("enabled_orgs"):
        p.write_text(config.sample_orgs_yaml(), encoding="utf-8")

    cmd_config_sync()

    # Perform shell integration in headless mode too
    rc_file = shell.detect_shell_profile()
    try:
        if shell.inject_shell_function(rc_file):
            console.print(f"[success]✅ Shell wrapper appended to {rc_file}[/]")
        else:
            console.print(f"✓ Shell wrapper already present in {rc_file}")
    except Exception as e:
        console.print(f"[warning]Could not inject shell wrapper: {e}[/]")

    return 0


def cmd_doctor(fix_path: bool = False) -> int:
    return int(doctor.run_diagnostics(fix_path))
